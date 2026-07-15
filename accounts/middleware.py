from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme


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
    """Laisse les utilisateurs consulter librement leur tableau de bord et les pages de
    dépôt/retrait/conversion (le dashboard doit toujours être visible). En revanche, dès
    qu'ils appuient sur un bouton pour VALIDER une action réelle (dépôt, retrait, conversion),
    un message clair s'affiche s'ils n'ont pas encore été vérifiés — l'action est bloquée,
    mais la navigation ne l'est jamais."""

    PROTECTED_APPS = {'wallets', 'moncash', 'cryptopay'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.user.is_authenticated and not request.user.is_staff:
            match = request.resolver_match
            app_name = match.app_name if match else None
            if app_name in self.PROTECTED_APPS:
                verification = getattr(request.user, 'identity_verification', None)
                status = verification.status if verification else 'NOT_SUBMITTED'
                if status != 'APPROVED':
                    messages.warning(
                        request,
                        "⚠️ Il faut vérifier votre identité avant de pouvoir effectuer cette action "
                        "(dépôt, retrait ou conversion). Rendez-vous dans Paramètres → Vérification "
                        "d'identité pour envoyer votre pièce d'identité et un selfie."
                    )
                    referer = request.META.get('HTTP_REFERER')
                    if referer and url_has_allowed_host_and_scheme(
                        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                    ):
                        return redirect(referer)
                    return redirect('wallets:dashboard')
        return self.get_response(request)
