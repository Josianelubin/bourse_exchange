"""
Paramètres Django pour bourse-exchange.
Sécurité durcie : HTTPS forcé, cookies sécurisés, protection brute-force (django-axes),
2FA (django-otp), CSP, headers de sécurité, montants en Decimal partout.
"""
import os
from pathlib import Path
import environ
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='INSECURE-CHANGE-ME')

# ── Debug ─────────────────────────────────────────────────────────────────────
# On teste si DEBUG est explicitement False/false/0/no, car une simple comparaison
# de chaîne rate quand la plateforme d'hébergement envoie 'False' avec une majuscule.
_debug_env = os.environ.get('DEBUG', 'True').strip().lower()
DEBUG = _debug_env not in ('false', '0', 'no', 'off')

# Protection : empêche le site de démarrer en production si la vraie clé secrète
# n'a jamais été configurée (ex: variable SECRET_KEY oubliée sur Render). Sans ce
# contrôle, le site tournerait avec une clé publique et connue de tous, ce qui rend
# les sessions et les jetons de sécurité falsifiables.
if not DEBUG and SECRET_KEY == 'INSECURE-CHANGE-ME':
    raise ImproperlyConfigured(
        "SECRET_KEY n'est pas configurée alors que DEBUG=False. "
        "Ajoute une vraie valeur pour SECRET_KEY dans les variables d'environnement avant de déployer."
    )

# ── Hosts & CSRF ──────────────────────────────────────────────────────────────
if DEBUG:
    ALLOWED_HOSTS = ['*']
    CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']
else:
    ALLOWED_HOSTS = os.environ.get(
        'ALLOWED_HOSTS', '.onrender.com,localhost,127.0.0.1'
    ).split(',')
    CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']
    # Ajoute chaque host de ALLOWED_HOSTS
    for _h in ALLOWED_HOSTS:
        _h = _h.strip()
        if _h and _h not in ('.onrender.com',):
            _origin = f"https://{_h.lstrip('.')}"
            if _origin not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(_origin)

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

# URL absolue du site, utilisée quand aucune requête HTTP n'est disponible pour construire
# l'URL nous-mêmes (ex: génération d'adresse de dépôt automatique à l'inscription, dans un
# signal Django). Priorité : variable d'environnement explicite, sinon déduite du domaine Render.
SITE_URL = env('SITE_URL', default='')
if not SITE_URL and RENDER_EXTERNAL_HOSTNAME:
    SITE_URL = f"https://{RENDER_EXTERNAL_HOSTNAME}"
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'rest_framework',
    'axes',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'csp',

    'accounts',
    'wallets',
    'moncash',
    'cryptopay',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',            # protection brute-force EN PREMIER
    'django.contrib.auth.backends.ModelBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',
    'axes.middleware.AxesMiddleware',        # protection brute-force EN DERNIER
    'accounts.middleware.BlockedUserMiddleware',
    'accounts.middleware.KYCRequiredMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- Base de données ---
# --- Base de données ---
# En local (Termux ou autre) : si DATABASE_URL n'est pas défini dans .env, on bascule
# automatiquement sur SQLite. Sur Render : DATABASE_URL est fourni automatiquement par
# render.yaml et pointe vers PostgreSQL. Le mode SSL n'est activé QUE pour PostgreSQL
# (sqlite plante si on lui passe sslmode).
_database_url = env('DATABASE_URL', default='')
_using_postgres = _database_url.startswith('postgres')

DATABASES = {
    'default': dj_database_url.config(
        default=_database_url or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=_using_postgres,
    )
}


AUTH_USER_MODEL = 'accounts.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr'
TIME_ZONE = 'America/Port-au-Prince'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# CompressedManifestStaticFilesStorage exige d'avoir lancé `collectstatic` au préalable
# (le manifeste staticfiles.json doit exister). En local/DEBUG, on utilise le stockage
# standard pour pouvoir lancer `runserver` directement sans étape supplémentaire.
if DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- Stockage persistant des fichiers media (Cloudinary), optionnel mais recommandé ---
# IMPORTANT pour les documents KYC : le disque de Render est effacé à chaque redéploiement.
# Sans ce réglage, les pièces d'identité/selfies uploadées seraient perdues au prochain déploiement.
_cloudinary_url = env('CLOUDINARY_URL', default='')
if _cloudinary_url:
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'wallets:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

# ============================================================
#  SÉCURITÉ — production (appliquée automatiquement si DEBUG=False)
# ============================================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # doit rester lisible par JS pour les requêtes AJAX avec CSRF token
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_AGE = 60 * 60 * 2  # 2h, déconnexion auto
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# --- django-axes : blocage après tentatives de connexion échouées ---
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # 1 heure de blocage
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = True

# --- Content Security Policy ---
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "https://cdn.jsdelivr.net", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:")
CSP_FONT_SRC = ("'self'", "https://cdn.jsdelivr.net")

# --- Email (vérification de compte, alertes) ---
# En local (DEBUG=True), affiche les e-mails dans la console au lieu d'exiger un vrai
# compte Gmail configuré — utile pour tester l'inscription et le mot de passe oublié
# sans rien configurer. En production, envoie réellement via Gmail SMTP.
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# --- Clés API tierces (jamais en dur, toujours en variables d'environnement) ---
MONCASH_CLIENT_ID = env('MONCASH_CLIENT_ID', default='')
MONCASH_CLIENT_SECRET = env('MONCASH_CLIENT_SECRET', default='')
MONCASH_MODE = env('MONCASH_MODE', default='sandbox')  # 'sandbox' ou 'live'

NOWPAYMENTS_API_KEY = env('NOWPAYMENTS_API_KEY', default='')
NOWPAYMENTS_IPN_SECRET = env('NOWPAYMENTS_IPN_SECRET', default='')

# --- Vérification d'e-mail à l'inscription (optionnel) ---
# Sans cette clé : vérification du format + du domaine (MX) uniquement, gratuite et automatique.
# Avec cette clé (AbstractAPI, https://www.abstractapi.com/email-verification-validation-api,
# offre gratuite disponible) : vérification quasi certaine que la boîte existe réellement.
EMAIL_VERIFICATION_API_KEY = env('EMAIL_VERIFICATION_API_KEY', default='')

# --- Mise à jour automatique des taux HTG/USDT/TRX (bouton dans l'admin) ---
# Clé gratuite à obtenir sur https://www.exchangerate-api.com/
EXCHANGE_RATE_API_KEY = env('EXCHANGE_RATE_API_KEY', default='')
# Clé Demo gratuite à obtenir sur https://www.coingecko.com/en/api/pricing
COINGECKO_API_KEY = env('COINGECKO_API_KEY', default='')
# Jeton secret pour autoriser l'appel automatique (cron externe) sans authentification admin
RATE_UPDATE_SECRET_TOKEN = env('RATE_UPDATE_SECRET_TOKEN', default='')

# --- Logging (traçabilité des actions sensibles) ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'transactions': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

JAZZMIN_SETTINGS = {
    "site_title": "Bourse Exchange Admin",
    "site_header": "Bourse Exchange",
    "site_brand": "Bourse Exchange",
    "site_logo": "img/nono.png",          # logo affiché en haut de la sidebar admin
    "login_logo": "img/nono.png",         # logo affiché sur la page de connexion admin
    "login_logo_dark": None,              # laissé vide : sinon Jazzmin affiche 2 logos superposés
    "site_icon": "img/nono.png",          # favicon utilisé dans /gestion-secrete/
    "site_logo_classes": "img-circle elevation-3",
    "welcome_sign": "Panneau d'administration - Bourse Exchange",
    "copyright": "Bourse Exchange",
    "search_model": ["accounts.CustomUser"],
    "show_ui_builder": False,
    "custom_css": "css/admin_custom.css",
    "custom_js": None,
    "changeform_format": "collapsible",
    "topmenu_links": [
        {"name": "Tableau de bord", "url": "admin:index"},
        {"name": "⚙️ Réglages & Frais", "url": "admin:wallets_sitesettings_changelist"},
        {"name": "💰 Revenus (compte bloqué)", "url": "admin:wallets_platformrevenue_changelist"},
        {"name": "Voir le site", "url": "/", "new_window": True},
    ],
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": True,
    "footer_small_text": True,
    "body_small_text": True,
    "brand_small_text": True,
    "sidebar_nav_small_text": True,
    "sidebar_nav_compact_style": True,
    "sidebar_nav_flat_style": True,
    "brand_colour": "navbar-dark",
    "accent": "accent-warning",
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-warning",
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
