"""
Client pour l'API MonCash Business (Digicel Haïti).
Documentation officielle : https://moncashbutton.digicelgroup.com/Moncash-business/document
Créer un compte marchand ici pour obtenir CLIENT_ID / CLIENT_SECRET :
https://moncashbutton.digicelgroup.com/
"""
import requests
from django.conf import settings

SANDBOX_BASE = "https://sandbox.moncashbutton.digicelgroup.com/Api"
LIVE_BASE = "https://moncashbutton.digicelgroup.com/Api"


class MonCashClient:
    def __init__(self):
        self.client_id = settings.MONCASH_CLIENT_ID
        self.client_secret = settings.MONCASH_CLIENT_SECRET
        self.base_url = LIVE_BASE if settings.MONCASH_MODE == 'live' else SANDBOX_BASE

    def _get_access_token(self):
        url = f"{self.base_url}/oauth/token"
        resp = requests.post(
            url,
            data={"scope": "read,write", "grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def create_payment(self, amount, order_id):
        """Crée une demande de paiement (dépôt) et retourne l'URL de redirection MonCash."""
        token = self._get_access_token()
        url = f"{self.base_url}/v1/CreatePayment"
        resp = requests.post(
            url,
            json={"amount": float(amount), "orderId": str(order_id)},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        payment_token = resp.json()["payment_token"]["token"]
        redirect_base = ("https://moncashbutton.digicelgroup.com" if settings.MONCASH_MODE == 'live'
                          else "https://sandbox.moncashbutton.digicelgroup.com")
        return f"{redirect_base}/Moncash-middleware/Payment/Redirect?token={payment_token}"

    def get_transaction_details(self, order_id):
        """Vérifie le statut réel d'un paiement auprès de MonCash (ne jamais faire confiance
        uniquement au callback : toujours re-vérifier côté serveur).
        Utilise RetrieveOrderPayment car nous recherchons par notre propre orderId
        (RetrieveTransactionPayment sert à chercher par transactionId MonCash, différent)."""
        token = self._get_access_token()
        url = f"{self.base_url}/v1/RetrieveOrderPayment"
        resp = requests.post(
            url,
            json={"orderId": str(order_id)},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_transaction_by_id(self, transaction_id):
        """Recherche un paiement par le transactionId propre à MonCash (utile en secours
        si le retour de paiement fournit ce paramètre au lieu de notre propre orderId)."""
        token = self._get_access_token()
        url = f"{self.base_url}/v1/RetrieveTransactionPayment"
        resp = requests.post(
            url,
            json={"transactionId": str(transaction_id)},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def send_payment(self, amount, receiver_phone, reference, description="Retrait Bourse Exchange"):
        """Retrait réel : envoie des fonds vers un numéro MonCash via l'endpoint officiel
        /v1/Transfert (nécessite les droits 'transfer' sur le compte marchand, activés par
        Digicel sur demande — contacte le support MonCash Business pour les activer).
        Les 4 champs (amount, receiver, desc, reference) sont TOUS obligatoires côté MonCash."""
        token = self._get_access_token()
        url = f"{self.base_url}/v1/Transfert"
        resp = requests.post(
            url,
            json={
                "amount": float(amount),
                "receiver": receiver_phone,
                "desc": description,
                "reference": str(reference),
            },
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get('transfer', data)
