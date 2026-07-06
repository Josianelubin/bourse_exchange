from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages


class BlockedUserMiddleware:
    """Déconnecte immédiatement tout utilisateur bloqué par un administrateur,
    même s'il possède déjà une session active."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, 'is_blocked', False):
            logout(request)
            messages.error(request, "Votre compte a été bloqué par un administrateur. Contactez le support.")
            return redirect('accounts:login')
        return self.get_response(request)


class KYCRequiredMiddleware:
    """Bloque l'accès à toutes les fonctionnalités financières du site (portefeuille,
    MonCash, crypto) tant que la vérification d'identité de l'utilisateur n'est pas
    approuvée par un administrateur. Le profil, les paramètres, la déconnexion et la
    page de vérification elle-même restent toujours accessibles."""

    # Apps dont l'accès nécessite un KYC approuvé
    PROTECTED_APPS = {'wallets', 'moncash', 'cryptopay'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_staff:
            match = request.resolver_match
            app_name = match.app_name if match else None
            if app_name in self.PROTECTED_APPS:
                verification = getattr(request.user, 'identity_verification', None)
                status = verification.status if verification else 'NOT_SUBMITTED'
                if status != 'APPROVED':
                    messages.warning(
                        request,
                        "Vous devez d'abord faire vérifier votre identité (pièce d'identité + selfie) "
                        "avant d'accéder aux fonctionnalités du site."
                    )
                    return redirect('accounts:kyc_upload')
        return self.get_response(request)
