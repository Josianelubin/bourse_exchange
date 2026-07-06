import json
import logging
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from wallets.models import CryptoWallet, CryptoCurrency, Transaction
from .services import NowPaymentsClient

logger = logging.getLogger('transactions')


@login_required
def deposit_address_view(request):
    """Affiche/génère l'adresse de dépôt crypto pour l'utilisateur (QR code inclus dans le template)."""
    currencies = CryptoCurrency.objects.filter(is_active=True)
    wallets = {w.currency_id: w for w in request.user.crypto_wallets.all()}
    return render(request, 'wallets/crypto_deposit.html', {
        'currencies': currencies, 'wallets': wallets,
    })


@login_required
def generate_address_view(request, currency_id):
    currency = CryptoCurrency.objects.get(id=currency_id, is_active=True)
    wallet, _ = CryptoWallet.objects.get_or_create(user=request.user, currency=currency)
    if not wallet.deposit_address:
        try:
            client = NowPaymentsClient()
            data = client.create_deposit_address(order_id=f"user{request.user.id}-{currency.symbol}",
                                                   pay_currency=currency.symbol)
            wallet.deposit_address = data.get('pay_address', '')
            wallet.save(update_fields=['deposit_address'])
        except Exception:
            logger.exception("Erreur génération adresse NOWPayments pour user=%s", request.user.id)
            messages.error(request, "Impossible de générer une adresse pour le moment.")
    return redirect('cryptopay:deposit_address')


@csrf_exempt
@require_POST
def nowpayments_webhook(request):
    """Webhook NOWPayments (IPN). Vérifie la signature HMAC avant toute action —
    c'est la seule source de confiance pour créditer un dépôt crypto réel."""
    signature = request.headers.get('x-nowpayments-sig', '')
    raw_body = request.body

    if not NowPaymentsClient.verify_ipn_signature(raw_body, signature):
        logger.warning("Webhook NOWPayments rejeté : signature invalide")
        return HttpResponseForbidden("Signature invalide")

    payload = json.loads(raw_body)
    status = payload.get('payment_status')
    order_id = payload.get('order_id', '')
    amount = payload.get('actually_paid') or payload.get('pay_amount')
    pay_currency = payload.get('pay_currency', '').upper()

    if status == 'finished' and amount:
        # str(amount) évite les erreurs d'arrondi binaire des float avant conversion en Decimal
        _credit_crypto_deposit(order_id, pay_currency, Decimal(str(amount)))

    return HttpResponse("OK")


@db_transaction.atomic
def _credit_crypto_deposit(order_id, pay_currency, amount):
    try:
        user_part = order_id.split('-')[0].replace('user', '')
        user_id = int(user_part)
    except (ValueError, IndexError):
        logger.error("order_id NOWPayments invalide: %s", order_id)
        return

    try:
        currency = CryptoCurrency.objects.get(symbol__iexact=pay_currency)
    except CryptoCurrency.DoesNotExist:
        logger.error("Devise inconnue reçue de NOWPayments: %s", pay_currency)
        return

    wallet = CryptoWallet.objects.select_for_update().get(user_id=user_id, currency=currency)
    wallet.balance += amount
    wallet.save(update_fields=['balance'])

    Transaction.objects.create(
        user_id=user_id, type=Transaction.Type.DEPOSIT_CRYPTO,
        status=Transaction.Status.COMPLETED, amount=amount,
        currency_label=currency.symbol, provider_payment_id=order_id,
    )
    logger.info("Dépôt crypto crédité: user=%s montant=%s devise=%s", user_id, amount, pay_currency)
