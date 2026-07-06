import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class SiteSettings(models.Model):
    """Réglages globaux modifiables depuis l'admin, sans toucher au code.
    Un seul enregistrement doit exister (singleton) : utilise SiteSettings.get_solo()."""
    moncash_withdraw_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2.50'),
        help_text="Frais appliqués sur les retraits HTG vers MonCash (%)"
    )
    moncash_deposit_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text="Frais appliqués sur les dépôts HTG via MonCash (%), 0 = gratuit"
    )
    auto_process_withdrawals = models.BooleanField(
        default=True,
        help_text="Si activé, les retraits HTG et crypto sont envoyés automatiquement "
                   "sans validation manuelle d'un administrateur. ATTENTION : irréversible en cas de fraude."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réglages du site"
        verbose_name_plural = "Réglages du site"

    def save(self, *args, **kwargs):
        self.pk = 1  # force le singleton : toujours le même enregistrement
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # empêche la suppression accidentelle du seul enregistrement de config

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Réglages du site"


class PlatformRevenue(models.Model):
    """Compte bloqué qui accumule les frais collectés par la plateforme (conversion,
    retrait, réseau), par devise. Ce n'est PAS un vrai portefeuille blockchain séparé :
    l'argent réel reste dans ton solde marchand NOWPayments (Custody) pour la crypto,
    et dans ton compte business MonCash pour les HTG. Ce modèle sert uniquement à savoir
    combien de ce solde global t'appartient réellement (ton profit) vs. ce qui appartient
    encore aux utilisateurs. Lecture seule dans l'admin — aucune modification manuelle."""
    currency_label = models.CharField(max_length=30, unique=True)  # 'HTG', 'USDTTRC20', 'TRX'...
    balance = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Revenu plateforme (compte bloqué)"
        verbose_name_plural = "Revenus plateforme (compte bloqué)"

    def __str__(self):
        return f"Revenu {self.currency_label} : {self.balance}"

    @classmethod
    def add_revenue(cls, currency_label, amount):
        """Crédite le compte bloqué. Doit être appelé à l'intérieur d'une transaction
        atomique existante (select_for_update pour éviter les pertes de frais en cas
        de deux écritures simultanées)."""
        if not amount or amount <= 0:
            return
        rev, _ = cls.objects.select_for_update().get_or_create(currency_label=currency_label)
        rev.balance += amount
        rev.save(update_fields=['balance'])


class CryptoNetwork(models.Model):
    """Ex: TRC20 (Tron), ERC20 (Ethereum), Polygon..."""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)  # ex: 'trx', 'eth', 'matic'
    withdraw_fee_fixed = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CryptoCurrency(models.Model):
    symbol = models.CharField(max_length=15, unique=True)  # ex: USDTTRC20 (identifiant NOWPayments)
    display_name = models.CharField(max_length=50)          # ex: USDT (TRC20)
    network = models.ForeignKey(CryptoNetwork, on_delete=models.PROTECT, related_name='currencies')
    conversion_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    withdraw_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    withdraw_fee_fixed = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'),
                                              help_text="Frais fixe de retrait, dans l'unité de cette devise (ex: 2 pour 2 USDT)")
    min_withdraw_amount = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'),
                                               help_text="Montant minimum de retrait autorisé, dans l'unité de cette devise")
    htg_exchange_rate = models.DecimalField(max_digits=20, decimal_places=4,
                                             help_text="1 unité de cette crypto = X HTG")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.display_name


class HTGWallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='htg_wallet')
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'),
                                   validators=[MinValueValidator(Decimal('0.00'))])
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Portefeuille HTG de {self.user.username}: {self.balance} HTG"


class CryptoWallet(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='crypto_wallets')
    currency = models.ForeignKey(CryptoCurrency, on_delete=models.PROTECT)
    balance = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0'),
                                   validators=[MinValueValidator(Decimal('0'))])
    deposit_address = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('user', 'currency')

    def __str__(self):
        return f"{self.user.username} - {self.currency.symbol}: {self.balance}"


class Transaction(models.Model):
    """Historique unifié: dépôts, retraits, conversions (HTG et crypto)."""

    class Type(models.TextChoices):
        DEPOSIT_HTG = 'DEPOSIT_HTG', 'Dépôt MonCash'
        WITHDRAW_HTG = 'WITHDRAW_HTG', 'Retrait MonCash'
        DEPOSIT_CRYPTO = 'DEPOSIT_CRYPTO', 'Dépôt Crypto'
        WITHDRAW_CRYPTO = 'WITHDRAW_CRYPTO', 'Retrait Crypto'
        CONVERT_HTG_TO_CRYPTO = 'CONVERT_HTG_TO_CRYPTO', 'Achat Crypto (HTG → Crypto)'
        CONVERT_CRYPTO_TO_HTG = 'CONVERT_CRYPTO_TO_HTG', 'Vente Crypto (Crypto → HTG)'
        CONVERT = 'CONVERT', 'Conversion'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        PROCESSING = 'PROCESSING', 'En traitement'
        COMPLETED = 'COMPLETED', 'Complété'
        FAILED = 'FAILED', 'Échoué'
        REJECTED = 'REJECTED', 'Rejeté'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=30, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    amount = models.DecimalField(max_digits=30, decimal_places=8)
    fee = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0'))
    currency_label = models.CharField(max_length=30)  # 'HTG' ou symbole crypto

    destination_address = models.CharField(max_length=255, blank=True)  # retrait crypto
    moncash_reference = models.CharField(max_length=100, blank=True)
    provider_payment_id = models.CharField(max_length=150, blank=True)  # id NOWPayments

    # Suppression "douce" côté utilisateur : masqué de SON historique sans effacer
    # la preuve comptable réelle (nécessaire pour audit et litiges financiers).
    hidden_by_user = models.BooleanField(default=False)

    admin_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'hidden_by_user'])]

    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} {self.currency_label} - {self.user.username}"
