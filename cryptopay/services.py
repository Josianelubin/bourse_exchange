"""
Client pour l'API NOWPayments (dépôts/retraits crypto réels, ex: USDT TRC20/ERC20).
Créer un compte marchand et obtenir la clé API ici : https://nowpayments.io
Documentation : https://documenter.getpostman.com/view/7907941/S1a32n38
Le secret IPN (NOWPAYMENTS_IPN_SECRET) sert à vérifier la signature des webhooks
pour empêcher qu'un attaquant simule un faux "paiement reçu".
"""
import hmac
import hashlib
import json
import requests
from django.conf import settings

BASE_URL = "https://api.nowpayments.io/v1"


class NowPaymentsClient:
    def __init__(self):
        self.api_key = settings.NOWPAYMENTS_API_KEY
        self.headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}

    def create_deposit_address(self, order_id, pay_currency):
        """Génère une adresse de dépôt dédiée pour un utilisateur/devise.
        (NOWPayments utilise le endpoint 'payment' avec invoice, adapté ici en mode adresse statique
        via le endpoint /payment pour recevoir des fonds vers le compte marchand.)"""
        resp = requests.post(
            f"{BASE_URL}/payment",
            headers=self.headers,
            json={
                "price_amount": 1,
                "price_currency": "usd",
                "pay_currency": pay_currency,
                "order_id": str(order_id),
                "ipn_callback_url": settings.NOWPAYMENTS_IPN_CALLBACK_URL if hasattr(settings, 'NOWPAYMENTS_IPN_CALLBACK_URL') else "",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def create_payout(self, address, currency, amount):
        """Retrait réel vers une adresse blockchain externe.
        Nécessite l'activation des payouts (2FA + whitelist IP) dans le tableau de bord NOWPayments."""
        resp = requests.post(
            f"{BASE_URL}/payout",
            headers=self.headers,
            json={"withdrawals": [{"address": address, "currency": currency, "amount": float(amount)}]},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def verify_ipn_signature(raw_body: bytes, received_signature: str) -> bool:
        """Vérifie que le webhook provient bien de NOWPayments (anti-usurpation).
        JAMAIS créditer un solde sans cette vérification."""
        secret = settings.NOWPAYMENTS_IPN_SECRET
        if not secret or not received_signature:
            return False
        payload = json.loads(raw_body)
        sorted_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        computed = hmac.new(secret.encode(), sorted_payload.encode(), hashlib.sha512).hexdigest()
        return hmac.compare_digest(computed, received_signature)
