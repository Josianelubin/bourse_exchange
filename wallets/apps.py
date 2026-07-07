from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_default_currencies(sender, **kwargs):
    """Crée automatiquement les réseaux et devises après chaque migration, pour que le site
    fonctionne dès qu'une clé NOWPayments est ajoutée, sans configuration manuelle obligatoire
    dans l'admin. Un administrateur peut toujours ajuster les taux de change et les frais
    ensuite dans /gestion-secrete/. Ne modifie JAMAIS une ligne qui existe déjà."""
    from .models import CryptoNetwork, CryptoCurrency
    from decimal import Decimal

    trc20, _ = CryptoNetwork.objects.get_or_create(
        code='trc20', defaults={'name': 'TRC20 (Tron)', 'is_active': True}
    )
    CryptoCurrency.objects.get_or_create(
        symbol='USDTTRC20',
        defaults={
            'display_name': 'USDT (TRC20)', 'network': trc20,
            'conversion_fee_percent': Decimal('2.00'), 'withdraw_fee_percent': Decimal('0.00'),
            'withdraw_fee_fixed': Decimal('2'), 'min_withdraw_amount': Decimal('10'),
            'htg_exchange_rate': Decimal('132.00'), 'is_active': True,
        },
    )
    CryptoCurrency.objects.get_or_create(
        symbol='TRX',
        defaults={
            'display_name': 'TRX (Tronx)', 'network': trc20,
            'conversion_fee_percent': Decimal('2.00'), 'withdraw_fee_percent': Decimal('0.00'),
            'withdraw_fee_fixed': Decimal('3'), 'min_withdraw_amount': Decimal('13'),
            'htg_exchange_rate': Decimal('13.00'), 'is_active': True,
        },
    )

    # --- Nouvelles cryptomonnaies : Bitcoin, Ethereum, Matic (Polygon), Solana ---
    # Frais de retrait 3% (pourcentage, pas de montant fixe), aucun minimum de retrait,
    # frais de conversion 2% (comme toutes les cryptos). À ajuster ensuite dans l'admin
    # avec les vrais taux du jour (le bouton "Actualiser les taux" gère déjà ces 4 devises).
    extra_currencies = [
        ('btc', 'Bitcoin', 'BTC (réseau Bitcoin)', Decimal('5500000.00')),
        ('eth', 'Ethereum (ERC20)', 'ETH (réseau ERC20)', Decimal('300000.00')),
        ('matic', 'Polygon', 'MATIC (réseau Polygon)', Decimal('90.00')),
        ('sol', 'Solana', 'SOL (réseau Solana)', Decimal('20000.00')),
    ]
    for symbol, network_name, display_name, default_rate in extra_currencies:
        network, _ = CryptoNetwork.objects.get_or_create(
            code=symbol, defaults={'name': network_name, 'is_active': True}
        )
        CryptoCurrency.objects.get_or_create(
            symbol=symbol.upper(),
            defaults={
                'display_name': display_name, 'network': network,
                'conversion_fee_percent': Decimal('2.00'), 'withdraw_fee_percent': Decimal('3.00'),
                'withdraw_fee_fixed': Decimal('0'), 'min_withdraw_amount': Decimal('0'),
                'htg_exchange_rate': default_rate, 'is_active': True,
            },
        )

    # Sur demande : seul USDT doit apparaître dans le dépôt, le retrait et le portefeuille
    # crypto. On désactive toutes les autres devises (elles restent en base, réactivables
    # à tout moment dans l'admin) plutôt que de les supprimer.
    CryptoCurrency.objects.exclude(symbol='USDTTRC20').update(is_active=False)


class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallets'

    def ready(self):
        post_migrate.connect(create_default_currencies, sender=self)
