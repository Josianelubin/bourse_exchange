from django.contrib import admin
from django.contrib import messages as django_messages
from .models import CryptoNetwork, CryptoCurrency, HTGWallet, CryptoWallet, Transaction, SiteSettings, PlatformRevenue


@admin.action(description="🔄 Actualiser les taux HTG automatiquement (prix réels du marché)")
def refresh_market_rates(modeladmin, request, queryset):
    from .rate_service import update_all_htg_rates
    try:
        results = update_all_htg_rates()
        if results:
            django_messages.success(request, "Taux mis à jour : " + " | ".join(results))
        else:
            django_messages.warning(request, "Aucune devise correspondante trouvée à mettre à jour.")
    except Exception as e:
        django_messages.error(request, f"Échec de la mise à jour automatique : {e}")


@admin.register(PlatformRevenue)
class PlatformRevenueAdmin(admin.ModelAdmin):
    """Compte bloqué : consultation uniquement, aucune création/modification/suppression manuelle."""
    list_display = ('currency_label', 'balance', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('moncash_withdraw_fee_percent', 'moncash_deposit_fee_percent', 'auto_process_withdrawals')

    def has_add_permission(self, request):
        # Un seul enregistrement de réglages : empêche d'en créer un deuxième.
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CryptoNetwork)
class CryptoNetworkAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'withdraw_fee_fixed', 'is_active')
    list_editable = ('withdraw_fee_fixed', 'is_active')


@admin.register(CryptoCurrency)
class CryptoCurrencyAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'symbol', 'network', 'htg_exchange_rate',
                     'conversion_fee_percent', 'withdraw_fee_percent', 'withdraw_fee_fixed',
                     'min_withdraw_amount', 'is_active')
    list_editable = ('htg_exchange_rate', 'conversion_fee_percent', 'withdraw_fee_percent',
                      'withdraw_fee_fixed', 'min_withdraw_amount', 'is_active')
    search_fields = ('display_name', 'symbol')
    actions = [refresh_market_rates]


@admin.register(HTGWallet)
class HTGWalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__username', 'user__email')


@admin.register(CryptoWallet)
class CryptoWalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'currency', 'balance', 'deposit_address')
    search_fields = ('user__username', 'user__email', 'deposit_address')
    list_filter = ('currency',)


@admin.action(description="✅ Marquer comme complété")
def mark_completed(modeladmin, request, queryset):
    queryset.update(status=Transaction.Status.COMPLETED)


@admin.action(description="❌ Rejeter la transaction")
def mark_rejected(modeladmin, request, queryset):
    queryset.update(status=Transaction.Status.REJECTED)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'status', 'amount', 'fee', 'currency_label', 'created_at')
    list_filter = ('type', 'status', 'currency_label', 'created_at')
    search_fields = ('user__username', 'user__email', 'moncash_reference',
                      'provider_payment_id', 'destination_address')
    readonly_fields = ('id', 'created_at', 'updated_at')
    actions = [mark_completed, mark_rejected]
