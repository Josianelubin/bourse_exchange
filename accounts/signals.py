import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from wallets.models import HTGWallet, CryptoWallet, CryptoCurrency
from .models import CustomUser, IdentityVerification

logger = logging.getLogger('transactions')


@receiver(post_save, sender=CustomUser)
def create_htg_wallet(sender, instance, created, **kwargs):
    """Crée automatiquement le portefeuille HTG à la création d'un compte."""
    if created:
        HTGWallet.objects.get_or_create(user=instance)


@receiver(post_save, sender=CustomUser)
def create_identity_verification(sender, instance, created, **kwargs):
    """Crée l'enregistrement de vérification d'identité (statut 'non soumis') pour
    chaque nouvel utilisateur."""
    if created:
        IdentityVerification.objects.get_or_create(user=instance)


@receiver(post_save, sender=CustomUser)
def create_crypto_wallets_with_address(sender, instance, created, **kwargs):
    """Crée automatiquement un portefeuille USDT et un portefeuille TRX pour chaque
    nouvel utilisateur, ET génère immédiatement une adresse de dépôt TRC20 réelle et
    valide via NOWPayments — sans action de l'utilisateur ni de l'administrateur.
    Si la clé API n'est pas encore configurée, l'adresse sera simplement vide et sera
    générée automatiquement plus tard, à la première visite de la page de dépôt."""
    if not created:
        return

    from cryptopay.services import NowPaymentsClient  # import différé, évite les imports circulaires

    if not settings.SITE_URL:
        # Impossible de construire une URL de callback IPN valide (aucune requête HTTP
        # disponible dans un signal, et SITE_URL non configurée) : NOWPayments rejette les
        # callbacks vides. L'adresse sera générée plus tard, à la première visite de la
        # page de dépôt (où l'URL réelle de la requête est disponible).
        logger.warning("SITE_URL non configurée : génération d'adresse à l'inscription ignorée "
                        "pour user=%s (sera générée à la première visite de la page de dépôt).",
                        instance.id)
        return

    for currency in CryptoCurrency.objects.filter(is_active=True):
        wallet, _ = CryptoWallet.objects.get_or_create(user=instance, currency=currency)
        if wallet.deposit_address or not settings.NOWPAYMENTS_API_KEY:
            continue
        try:
            client = NowPaymentsClient()
            callback_url = f"{settings.SITE_URL}/crypto/webhook/nowpayments/"
            data = client.create_deposit_address(
                order_id=f"user{instance.id}-{currency.symbol}",
                pay_currency=currency.symbol,
                ipn_callback_url=callback_url,
            )
            address = data.get('pay_address', '')
            if address:
                wallet.deposit_address = address
                wallet.save(update_fields=['deposit_address'])
        except Exception:
            # On ne bloque jamais la création du compte si NOWPayments est indisponible :
            # l'adresse sera générée automatiquement au premier accès à la page de dépôt.
            logger.warning("Adresse de dépôt %s non générée automatiquement pour user=%s",
                            currency.symbol, instance.id)
