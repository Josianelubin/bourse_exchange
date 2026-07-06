from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from .models import CustomUser, AccountActivityLog, IdentityVerification


@admin.action(description="✅ Approuver la vérification (supprime les images ensuite)")
def approve_kyc(modeladmin, request, queryset):
    for kyc in queryset:
        kyc.status = IdentityVerification.Status.APPROVED
        kyc.reviewed_at = timezone.now()
        if kyc.id_document_front:
            kyc.id_document_front.delete(save=False)
        if kyc.id_document_back:
            kyc.id_document_back.delete(save=False)
        if kyc.selfie:
            kyc.selfie.delete(save=False)
        kyc.save()


@admin.action(description="❌ Rejeter la vérification (supprime les images, l'utilisateur devra renvoyer)")
def reject_kyc(modeladmin, request, queryset):
    for kyc in queryset:
        kyc.status = IdentityVerification.Status.REJECTED
        kyc.reviewed_at = timezone.now()
        if kyc.id_document_front:
            kyc.id_document_front.delete(save=False)
        if kyc.id_document_back:
            kyc.id_document_back.delete(save=False)
        if kyc.selfie:
            kyc.selfie.delete(save=False)
        kyc.save()


@admin.register(IdentityVerification)
class IdentityVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'submitted_at', 'reviewed_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user', 'submitted_at', 'reviewed_at',
                        'id_document_front_preview', 'id_document_back_preview', 'selfie_preview')
    fields = ('user', 'status', 'rejection_reason',
              'id_document_front_preview', 'id_document_back_preview', 'selfie_preview',
              'submitted_at', 'reviewed_at')
    actions = [approve_kyc, reject_kyc]

    def id_document_front_preview(self, obj):
        if obj.id_document_front:
            return format_html('<img src="{}" style="max-width:320px;border-radius:8px;">', obj.id_document_front.url)
        return "Aucun document (supprimé ou non envoyé)"
    id_document_front_preview.short_description = "Pièce d'identité — recto"

    def id_document_back_preview(self, obj):
        if obj.id_document_back:
            return format_html('<img src="{}" style="max-width:320px;border-radius:8px;">', obj.id_document_back.url)
        return "Aucun document (supprimé ou non envoyé)"
    id_document_back_preview.short_description = "Pièce d'identité — verso"

    def selfie_preview(self, obj):
        if obj.selfie:
            return format_html('<img src="{}" style="max-width:320px;border-radius:8px;">', obj.selfie.url)
        return "Aucun selfie (supprimé ou non envoyé)"
    selfie_preview.short_description = "Selfie"

    def has_add_permission(self, request):
        return False  # créé automatiquement à l'inscription, jamais manuellement


@admin.action(description="🔒 Bloquer les utilisateurs sélectionnés")
def block_users(modeladmin, request, queryset):
    queryset.update(is_blocked=True)


@admin.action(description="🔓 Débloquer les utilisateurs sélectionnés")
def unblock_users(modeladmin, request, queryset):
    queryset.update(is_blocked=False, blocked_reason='')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Barre de recherche admin : nom d'utilisateur, email, téléphone
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    list_display = (
        'username', 'email', 'phone_number', 'is_email_verified',
        'status_badge', 'wallet_balance', 'date_joined', 'last_login',
    )
    list_filter = ('is_blocked', 'is_email_verified', 'is_staff', 'is_active', 'date_joined')
    actions = [block_users, unblock_users]
    readonly_fields = ('date_joined', 'last_login', 'created_at', 'last_login_ip')

    fieldsets = UserAdmin.fieldsets + (
        ('Informations Bourse Exchange', {
            'fields': ('phone_number', 'is_email_verified', 'is_blocked', 'blocked_reason',
                       'two_factor_enabled', 'last_login_ip', 'created_at')
        }),
    )

    def status_badge(self, obj):
        if obj.is_blocked:
            return format_html('<span style="color:white;background:#dc3545;padding:3px 8px;border-radius:4px;">{}</span>', "Bloqué")
        return format_html('<span style="color:white;background:#28a745;padding:3px 8px;border-radius:4px;">{}</span>', "Actif")
    status_badge.short_description = "Statut"

    def wallet_balance(self, obj):
        wallet = getattr(obj, 'htg_wallet', None)
        if wallet:
            return f"{wallet.balance} HTG"
        return "—"
    wallet_balance.short_description = "Solde HTG"


@admin.register(AccountActivityLog)
class AccountActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = [f.name for f in AccountActivityLog._meta.fields]

    def has_add_permission(self, request):
        return False  # journal en lecture seule, non modifiable
