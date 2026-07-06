import logging
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.shortcuts import render, redirect
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from wallets.forms import MonCashDepositForm, MonCashWithdrawForm
from wallets.models import Transaction, HTGWallet, SiteSettings, PlatformRevenue
from .services import MonCashClient

logger = logging.getLogger('transactions')


@login_required
@ratelimit(key='user', rate='6/m', block=True)
def deposit_view(request):
    if request.method == 'POST':
        form = MonCashDepositForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            tx = Transaction.objects.create(
                user=request.user, type=Transaction.Type.DEPOSIT_HTG,
                status=Transaction.Status.PENDING, amount=amount, currency_label='HTG',
            )
            try:
                client = MonCashClient()
                redirect_url = client.create_payment(amount, order_id=tx.id)
            except Exception:
                logger.exception("Erreur MonCash CreatePayment pour tx=%s", tx.id)
                tx.status = Transaction.Status.FAILED
                tx.save(update_fields=['status'])
                messages.error(request, "Impossible de contacter MonCash pour le moment. Réessayez plus tard.")
                return redirect('wallets:dashboard')
            return redirect(redirect_url)
    else:
        form = MonCashDepositForm()
    fee_percent = SiteSettings.get_solo().moncash_deposit_fee_percent
    return render(request, 'wallets/moncash_deposit.html', {'form': form, 'fee_percent': fee_percent})


@login_required
def deposit_return_view(request):
    """Page de retour après paiement MonCash. Le solde n'est JAMAIS crédité ici :
    on ne fait confiance qu'à la vérification serveur-à-serveur (voir verify_and_credit).
    MonCash peut renvoyer soit notre propre orderId, soit son propre transactionId selon
    la configuration du compte marchand — les deux cas sont gérés."""
    order_id = request.GET.get('orderId') or request.GET.get('order_id')
    transaction_id = request.GET.get('transactionId') or request.GET.get('transaction_id')

    if order_id:
        return verify_and_credit(request, order_id=order_id)
    if transaction_id:
        return verify_and_credit(request, transaction_id=transaction_id)

    messages.warning(request, "Retour MonCash incomplet — vérifiez la configuration de "
                               "l'URL de retour dans votre portail marchand MonCash Business.")
    return redirect('wallets:dashboard')


@db_transaction.atomic
def verify_and_credit(request, order_id=None, transaction_id=None):
    client = MonCashClient()
    try:
        if order_id:
            tx = Transaction.objects.select_for_update().get(id=order_id, type=Transaction.Type.DEPOSIT_HTG)
            details = client.get_transaction_details(order_id)
        else:
            details = client.get_transaction_by_id(transaction_id)
            payment_ref = details.get('payment', {}).get('reference')
            if not payment_ref:
                raise Transaction.DoesNotExist
            tx = Transaction.objects.select_for_update().get(id=payment_ref, type=Transaction.Type.DEPOSIT_HTG)
    except Transaction.DoesNotExist:
        messages.error(request, "Transaction introuvable.")
        return redirect('wallets:dashboard')

    if tx.status == Transaction.Status.COMPLETED:
        messages.info(request, "Ce dépôt a déjà été crédité.")
        return redirect('wallets:dashboard')

    try:
        payment = details.get('payment', {})
        # MonCash renvoie message == 'successful' pour un paiement confirmé
        if payment.get('message') == 'successful':
            wallet = HTGWallet.objects.select_for_update().get(user=tx.user)
            fee = tx.amount * (SiteSettings.get_solo().moncash_deposit_fee_percent / Decimal('100'))
            net_amount = tx.amount - fee
            wallet.balance += net_amount
            wallet.save(update_fields=['balance'])
            tx.status = Transaction.Status.COMPLETED
            tx.fee = fee
            tx.moncash_reference = str(payment.get('transaction_id', ''))
            tx.save(update_fields=['status', 'fee', 'moncash_reference'])
            PlatformRevenue.add_revenue('HTG', fee)
            messages.success(request, "Dépôt confirmé et crédité sur votre portefeuille HTG.")
        else:
            tx.status = Transaction.Status.FAILED
            tx.save(update_fields=['status'])
            messages.error(request, "Le paiement MonCash n'a pas été confirmé.")
    except Exception:
        logger.exception("Erreur vérification MonCash pour tx=%s", tx.id)
        messages.error(request, "Impossible de vérifier ce paiement pour le moment.")
    return redirect('wallets:dashboard')


@login_required
@ratelimit(key='user', rate='4/m', block=True)
@db_transaction.atomic
def withdraw_view(request):
    """Retrait HTG vers MonCash — ENTIÈREMENT AUTOMATIQUE : dès que le solde est suffisant,
    les fonds sont envoyés immédiatement via l'API MonCash (send_payment), sans validation
    d'un administrateur. En cas d'échec de l'envoi, le solde est remboursé automatiquement."""
    if request.method == 'POST':
        form = MonCashWithdrawForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            phone = form.cleaned_data['moncash_phone']
            settings_obj = SiteSettings.get_solo()
            wallet = HTGWallet.objects.select_for_update().get(user=request.user)

            fee = amount * (settings_obj.moncash_withdraw_fee_percent / Decimal('100'))
            total = amount + fee
            if wallet.balance < total:
                messages.error(request, "Solde HTG insuffisant.")
                return redirect('moncash:withdraw')

            wallet.balance -= total
            wallet.save(update_fields=['balance'])

            tx = Transaction.objects.create(
                user=request.user, type=Transaction.Type.WITHDRAW_HTG,
                status=Transaction.Status.PROCESSING, amount=amount, fee=fee,
                currency_label='HTG', destination_address=phone,
            )

            try:
                client = MonCashClient()
                result = client.send_payment(
                    amount, phone,
                    reference=tx.id,
                    description=f"Retrait Bourse Exchange #{tx.id}",
                )
                tx.status = Transaction.Status.COMPLETED
                tx.moncash_reference = str(result.get('transaction_id', ''))
                tx.save(update_fields=['status', 'moncash_reference'])
                logger.info("Retrait MonCash auto-exécuté user=%s montant=%s", request.user.id, amount)
                PlatformRevenue.add_revenue('HTG', fee)
                messages.success(request, "Retrait envoyé avec succès sur votre compte MonCash.")
            except Exception:
                # Échec d'envoi réel : on rembourse automatiquement pour ne pas perdre les fonds.
                logger.exception("Échec envoi MonCash pour tx=%s, remboursement du solde", tx.id)
                wallet.balance += total
                wallet.save(update_fields=['balance'])
                tx.status = Transaction.Status.FAILED
                tx.save(update_fields=['status'])
                messages.error(request, "Le retrait a échoué et votre solde a été remboursé. Réessayez plus tard.")
            return redirect('wallets:history')
    else:
        form = MonCashWithdrawForm()
    return render(request, 'wallets/moncash_withdraw.html', {'form': form, 'fee_percent': SiteSettings.get_solo().moncash_withdraw_fee_percent})
