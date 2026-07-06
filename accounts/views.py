import logging
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from django.http import JsonResponse
from .forms import RegisterForm, ProfileForm, DeleteAccountForm, IdentityVerificationForm
from .models import CustomUser, AccountActivityLog

logger = logging.getLogger('transactions')


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


@ratelimit(key='ip', rate='5/h', block=True)
def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email'].lower()
            user.is_active = True
            user.save()
            link = request.build_absolute_uri(
                reverse('accounts:verify_email', args=[user.email_verification_token])
            )
            try:
                send_mail(
                    "Vérifiez votre compte Bourse Exchange",
                    f"Bonjour {user.username},\n\nConfirmez votre compte : {link}\n\nSi vous n'êtes pas à l'origine de cette inscription, ignorez ce message.",
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            except Exception:
                logger.warning("Échec envoi email de vérification pour %s", user.email)
            messages.success(request, "Compte créé ! Vérifiez votre e-mail pour l'activer.")
            AccountActivityLog.objects.create(user=user, action='REGISTER', ip_address=_client_ip(request))
            return redirect('accounts:login')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def verify_email_view(request, token):
    user = get_object_or_404(CustomUser, email_verification_token=token)
    user.is_email_verified = True
    user.save(update_fields=['is_email_verified'])
    messages.success(request, "E-mail vérifié avec succès. Vous pouvez vous connecter.")
    return redirect('accounts:login')


@ratelimit(key='ip', rate='10/m', block=True)
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_blocked:
                messages.error(request, "Ce compte est bloqué. Contactez le support.")
                return redirect('accounts:login')
            login(request, user)
            user.last_login_ip = _client_ip(request)
            user.save(update_fields=['last_login_ip'])
            AccountActivityLog.objects.create(user=user, action='LOGIN', ip_address=_client_ip(request))
            return redirect('wallets:dashboard')
        messages.error(request, "Identifiants incorrects.")
    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    AccountActivityLog.objects.create(user=request.user, action='LOGOUT', ip_address=_client_ip(request))
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def settings_view(request):
    """Paramètres du compte : sécurité, notifications, 2FA (activation à compléter avec django-otp)."""
    return render(request, 'accounts/settings.html')


@login_required
def delete_account_view(request):
    if request.method == 'POST':
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            if not request.user.check_password(form.cleaned_data['password']):
                messages.error(request, "Mot de passe incorrect.")
            else:
                user = request.user
                logger.info("Suppression du compte utilisateur id=%s", user.id)
                logout(request)
                user.delete()
                messages.success(request, "Votre compte a été supprimé définitivement.")
                return redirect('accounts:login')
    else:
        form = DeleteAccountForm()
    return render(request, 'accounts/delete_account.html', {'form': form})


@ratelimit(key='ip', rate='5/h', block=True)
def password_reset_view(request):
    """Enveloppe la vue standard de Django avec une limite de débit, pour empêcher
    qu'un attaquant spamme les e-mails de réinitialisation vers n'importe quel utilisateur."""
    from django.contrib.auth import views as auth_views
    return auth_views.PasswordResetView.as_view(template_name='accounts/password_reset.html')(request)


@login_required
def kyc_upload_view(request):
    """Page d'envoi de la pièce d'identité + du selfie. Reste accessible même si le
    KYC n'est pas encore approuvé (sinon l'utilisateur serait bloqué sans pouvoir
    jamais envoyer ses documents)."""
    from django.utils import timezone
    from .models import IdentityVerification
    verification, _ = IdentityVerification.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = IdentityVerificationForm(request.POST, request.FILES, instance=verification)
        if form.is_valid():
            kyc = form.save(commit=False)
            kyc.status = kyc.Status.PENDING
            kyc.submitted_at = timezone.now()
            kyc.rejection_reason = ''
            kyc.save()
            messages.success(request, "Documents envoyés. Un administrateur va vérifier votre identité.")
            return redirect('accounts:kyc_upload')
    else:
        form = IdentityVerificationForm(instance=verification)

    return render(request, 'accounts/kyc_upload.html', {'form': form, 'verification': verification})


@ratelimit(key='ip', rate='20/m', block=True)
def check_email_view(request):
    """Endpoint AJAX appelé pendant la saisie du formulaire d'inscription pour afficher
    en direct 'E-mail valide' / 'E-mail invalide' avant même de soumettre le formulaire."""
    email = request.GET.get('email', '').strip().lower()
    if not email or '@' not in email:
        return JsonResponse({'valid': False, 'message': "Adresse incomplète."})

    if CustomUser.objects.filter(email=email).exists():
        return JsonResponse({'valid': False, 'message': "Cette adresse est déjà utilisée."})

    from .services import verify_email_exists
    is_valid, message = verify_email_exists(email)
    return JsonResponse({'valid': is_valid, 'message': message})
