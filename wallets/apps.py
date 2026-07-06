from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_default_currencies(sender, **kwargs):
    """Crée automatiquement le réseau TRC20 et les devises USDT/TRX après chaque migration,
    pour que le site fonctionne dès qu'une clé NOWPayments est ajoutée, sans configuration
    manuelle obligatoire dans l'admin. Un administrateur peut toujours ajuster les taux de
    change et les frais ensuite dans /gestion-secrete/."""
    from .models import CryptoNetwork, CryptoCurrency
    from decimal import Decimal

    network, _ = CryptoNetwork.objects.get_or_create(
        code='trc20', defaults={'name': 'TRC20 (Tron)', 'is_active': True}
    )
    CryptoCurrency.objects.get_or_create(
        symbol='USDTTRC20',
        defaults={
            'display_name': 'USDT (TRC20)', 'network': network,
            'conversion_fee_percent': Decimal('1.00'), 'withdraw_fee_percent': Decimal('0.00'),
            'withdraw_fee_fixed': Decimal('2'), 'min_withdraw_amount': Decimal('10'),
            'htg_exchange_rate': Decimal('132.00'), 'is_active': True,
        },
    )
    CryptoCurrency.objects.get_or_create(
        symbol='TRX',
        defaults={
            'display_name': 'TRX (Tronx)', 'network': network,
            'conversion_fee_percent': Decimal('1.00'), 'withdraw_fee_percent': Decimal('0.00'),
            'withdraw_fee_fixed': Decimal('3'), 'min_withdraw_amount': Decimal('13'),
            'htg_exchange_rate': Decimal('13.00'), 'is_active': True,
        },
    )


class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallets'

    def ready(self):
        post_migrate.connect(create_default_currencies, sender=self)
