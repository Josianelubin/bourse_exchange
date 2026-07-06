import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Utilisateur personnalisé avec statut de blocage, vérification e-mail et 2FA."""
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_email_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False, help_text="Bloqué par un administrateur")
    blocked_reason = models.CharField(max_length=255, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.username

    class Meta:
        ordering = ['-created_at']


class IdentityVerification(models.Model):
    """Vérification d'identité (KYC) : pièce d'identité + selfie.
    Tant que le statut n'est pas APPROVED, l'utilisateur ne peut accéder à aucune
    fonctionnalité financière du site (voir accounts.middleware.KYCRequiredMiddleware).
    Les images sont supprimées automatiquement dès qu'un administrateur les traite
    (approuvées ou rejetées) — on ne conserve jamais un document d'identité plus
    longtemps que nécessaire."""

    class Status(models.TextChoices):
        NOT_SUBMITTED = 'NOT_SUBMITTED', 'Non soumis'
        PENDING = 'PENDING', 'En attente de vérification'
        APPROVED = 'APPROVED', 'Vérifié'
        REJECTED = 'REJECTED', 'Rejeté'

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='identity_verification')
    id_document_front = models.ImageField(upload_to='kyc/id_documents/', null=True, blank=True,
                                           help_text="Carte d'identité ou passeport — recto")
    id_document_back = models.ImageField(upload_to='kyc/id_documents/', null=True, blank=True,
                                          help_text="Carte d'identité ou passeport — verso")
    selfie = models.ImageField(upload_to='kyc/selfies/', null=True, blank=True,
                                help_text="Selfie (caméra ou fichier)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_SUBMITTED)
    rejection_reason = models.CharField(max_length=255, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Vérification d'identité (KYC)"
        verbose_name_plural = "Vérifications d'identité (KYC)"

    def __str__(self):
        return f"KYC {self.user.username} — {self.get_status_display()}"


class AccountActivityLog(models.Model):
    """Journal des actions sensibles pour audit (connexion, blocage, suppression...)."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.created_at:%Y-%m-%d %H:%M}"
