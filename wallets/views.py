import logging
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from .models import Transaction, CryptoWallet, PlatformRevenue, CryptoCurrency, HTGWallet
from .forms import ConvertForm, CryptoWithdrawForm
from cryptopay.services import NowPaymentsClient

logger = logging.getLogger('transactions')


@login_required
def dashboard_view(request):
    htg_wallet = request.user.htg_wallet
    crypto_wallets = request.user.crypto_wallets.select_related('currency').filter(currency__is_active=True)
    recent_tx = request.user.transactions.filter(hidden_by_user=False)[:8]
    return render(request, 'wallets/dashboard.html', {
        'htg_wallet': htg_wallet,
        'crypto_wallets': crypto_wallets,
        'recent_tx': recent_tx,
    })


@login_required
def history_view(request):
    # L'utilisateur ne voit jamais les transactions qu'il a masquées de son historique.
    tx_list = request.user.transactions.filter(hidden_by_user=False)
    return render(request, 'wallets/history.html', {'transactions': tx_list})


@login_required
def delete_transaction_view(request, tx_id):
    """Bouton 'Supprimer' de l'historique utilisateur.
    SUPPRESSION DÉFINITIVE ET COMPLÈTE : la ligne est effacée de la base de données,
    aucune trace n'est conservée (ni pour l'utilisateur, ni pour l'admin).
    ATTENTION : en cas de litige futur sur cette transaction (ex: 'je n'ai jamais reçu
    cet argent'), il ne sera plus possible de la retrouver pour trancher."""
    tx = get_object_or_404(Transaction, id=tx_id, user=request.user)
    if request.method == 'POST':
        tx.delete()
        messages.success(request, "Transaction supprimée définitivement.")
        return redirect('wallets:history')
    return render(request, 'wallets/confirm_delete_transaction.html', {'tx': tx})


def _currency_rate(label):
    """1 unité de cette devise = X HTG. HTG vaut toujours 1 par définition."""
    if label == 'HTG':
        return Decimal('1')
    return CryptoCurrency.objects.get(symbol=label).htg_exchange_rate


def _currency_fee_percent(label):
    """Frais de conversion (%) appliqué pour cette devise. HTG n'a pas de frais propre."""
    if label == 'HTG':
        return Decimal('0')
    return CryptoCurrency.objects.get(symbol=label).conversion_fee_percent


def _get_wallet_locked(user, label):
    """Retourne le portefeuille (HTG ou crypto) correspondant à la devise, verrouillé
    (select_for_update) pour éviter toute condition de course sur le solde."""
    if label == 'HTG':
        return HTGWallet.objects.select_for_update().get(user=user)
    currency = CryptoCurrency.objects.get(symbol=label)
    wallet, _ = CryptoWallet.objects.select_for_update().get_or_create(user=user, currency=currency)
    return wallet


@login_required
@ratelimit(key='user', rate='10/m', block=True)
@db_transaction.atomic
def convert_view(request):
    """Conversion entre N'IMPORTE QUELLE paire de devises actives (HTG, USDT, TRX, et toute
    devise ajoutée plus tard) : l'utilisateur choisit librement ce qu'il paie et ce qu'il
    reçoit. Le calcul passe toujours par un équivalent HTG en interne :
    montant payé -> valeur HTG -> frais côté devise payée -> frais côté devise reçue ->
    montant reçu. Verrouillage des deux portefeuilles pour éviter les conditions de course."""
    if request.method == 'POST':
        form = ConvertForm(request.POST)
        if form.is_valid():
            pay_label = form.cleaned_data['pay_currency']
            receive_label = form.cleaned_data['receive_currency']
            amount = form.cleaned_data['amount']

            pay_wallet = _get_wallet_locked(request.user, pay_label)
            receive_wallet = _get_wallet_locked(request.user, receive_label)

            if pay_wallet.balance < amount:
                messages.error(request, f"Solde {pay_label} insuffisant.")
                return redirect('wallets:convert')

            pay_rate = _currency_rate(pay_label)
            receive_rate = _currency_rate(receive_label)
            pay_fee_percent = _currency_fee_percent(pay_label)
            receive_fee_percent = _currency_fee_percent(receive_label)

            htg_value = amount * pay_rate
            fee_pay_side = htg_value * (pay_fee_percent / Decimal('100'))
            after_fee_pay = htg_value - fee_pay_side
            fee_receive_side = after_fee_pay * (receive_fee_percent / Decimal('100'))
            after_fee_receive = after_fee_pay - fee_receive_side
            received = after_fee_receive / receive_rate
            total_fee_htg = fee_pay_side + fee_receive_side

            pay_wallet.balance -= amount
            receive_wallet.balance += received
            pay_wallet.save(update_fields=['balance'])
            receive_wallet.save(update_fields=['balance'])

            Transaction.objects.create(
                user=request.user, type=Transaction.Type.CONVERT,
                status=Transaction.Status.COMPLETED, amount=amount, fee=total_fee_htg,
                currency_label=f"{pay_label}→{receive_label}",
            )
            PlatformRevenue.add_revenue('HTG', total_fee_htg)
            logger.info("Conversion %s->%s pour user=%s montant=%s",
                        pay_label, receive_label, request.user.id, amount)
            messages.success(
                request,
                f"Converti avec succès : {amount} {pay_label} → {received:.8f} {receive_label} "
                f"(frais totaux : {total_fee_htg:.2f} HTG équivalent)."
            )
            return redirect('wallets:dashboard')
        else:
            # Si le formulaire est invalide (ex: même devise des deux côtés, montant vide),
            # le message d'erreur est toujours affiché — le bouton ne "fait rien" en silence.
            error_text = " ".join(
                f"{field} : {', '.join(errs)}" for field, errs in form.errors.items()
            ) or "Veuillez vérifier le montant et les devises sélectionnées."
            messages.error(request, f"Conversion impossible — {error_text}")
    else:
        form = ConvertForm()
    currencies = CryptoCurrency.objects.filter(is_active=True)
    return render(request, 'wallets/convert.html', {'form': form, 'currencies': currencies})


@login_required
@ratelimit(key='user', rate='5/m', block=True)
@db_transaction.atomic
def crypto_withdraw_view(request):
    """Retrait crypto — ENTIÈREMENT AUTOMATIQUE : dès validation du formulaire, les fonds
    sont envoyés immédiatement sur la blockchain via NOWPayments (create_payout), sans
    validation d'un administrateur. En cas d'échec de l'envoi, le solde est remboursé
    automatiquement. ATTENTION : un envoi blockchain réussi est irréversible."""
    if request.method == 'POST':
        form = CryptoWithdrawForm(request.POST)
        if form.is_valid():
            currency = form.cleaned_data['currency']
            amount = form.cleaned_data['amount']
            address = form.cleaned_data['destination_address']

            if amount < currency.min_withdraw_amount:
                messages.error(
                    request,
                    f"Le retrait minimum pour {currency.symbol} est de {currency.min_withdraw_amount} {currency.symbol}."
                )
                return redirect('wallets:crypto_withdraw')

            wallet = CryptoWallet.objects.select_for_update().get(user=request.user, currency=currency)
            network_fee = currency.network.withdraw_fee_fixed
            percent_fee = amount * (currency.withdraw_fee_percent / Decimal('100'))
            fee = percent_fee + currency.withdraw_fee_fixed + network_fee
            total_debit = amount + fee
            if wallet.balance < total_debit:
                messages.error(request, "Solde insuffisant pour ce retrait (frais inclus).")
                return redirect('wallets:crypto_withdraw')

            wallet.balance -= total_debit
            wallet.save(update_fields=['balance'])

            tx = Transaction.objects.create(
                user=request.user, type=Transaction.Type.WITHDRAW_CRYPTO,
                status=Transaction.Status.PROCESSING, amount=amount, fee=fee,
                currency_label=currency.symbol, destination_address=address,
            )

            try:
                client = NowPaymentsClient()
                result = client.create_payout(address, currency.symbol, amount)
                tx.status = Transaction.Status.COMPLETED
                tx.provider_payment_id = str(result.get('id', result.get('batch_withdrawal_id', '')))
                tx.save(update_fields=['status', 'provider_payment_id'])
                logger.info("Retrait crypto auto-exécuté user=%s montant=%s devise=%s",
                            request.user.id, amount, currency.symbol)
                PlatformRevenue.add_revenue(currency.symbol, fee)  # frais % + frais réseau TRC20
                messages.success(request, "Retrait envoyé avec succès sur la blockchain.")
            except Exception:
                logger.exception("Échec envoi NOWPayments pour tx=%s, remboursement du solde", tx.id)
                wallet.balance += total_debit
                wallet.save(update_fields=['balance'])
                tx.status = Transaction.Status.FAILED
                tx.save(update_fields=['status'])
                messages.error(request, "Le retrait a échoué et votre solde a été remboursé. Réessayez plus tard.")
            return redirect('wallets:history')
    else:
        form = CryptoWithdrawForm()
    return render(request, 'wallets/crypto_withdraw.html', {
        'form': form, 'currencies': CryptoCurrency.objects.filter(is_active=True),
    })


@csrf_exempt
def auto_update_rates_view(request):
    """Point d'accès pour automatiser vraiment la mise à jour des prix HTG/USDT/TRX
    (ex: toutes les heures), sans avoir besoin de Celery/Redis. À appeler depuis un
    service de cron externe GRATUIT (ex: cron-job.org) avec le bon jeton secret :

        GET https://TON-DOMAINE.onrender.com/portefeuille/actualiser-taux/?token=TON_JETON

    Protégé par RATE_UPDATE_SECRET_TOKEN (variable d'environnement) : sans le bon jeton,
    la requête est rejetée. Ne fonctionne pas si RATE_UPDATE_SECRET_TOKEN n'est pas défini."""
    expected_token = settings.RATE_UPDATE_SECRET_TOKEN
    if not expected_token or request.GET.get('token') != expected_token:
        return HttpResponseForbidden("Jeton invalide ou non configuré.")

    from .rate_service import update_all_htg_rates
    try:
        results = update_all_htg_rates()
        logger.info("Taux actualisés automatiquement : %s", results)
        return JsonResponse({'success': True, 'updated': results})
    except Exception as e:
        logger.exception("Échec de l'actualisation automatique des taux")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
