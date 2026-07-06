from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView


def _root_redirect():
    """Racine du site : envoie l'utilisateur connecté vers son tableau de bord,
    sinon vers la page de connexion."""
    return RedirectView.as_view(pattern_name='wallets:dashboard', permanent=False)


urlpatterns = [
    path('gestion-secrete/', admin.site.urls),
    path('', login_required(_root_redirect(), login_url='accounts:login'), name='home'),
    path('', include('accounts.urls')),
    path('portefeuille/', include('wallets.urls')),
    path('moncash/', include('moncash.urls')),
    path('crypto/', include('cryptopay.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
