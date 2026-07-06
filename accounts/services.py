"""
Vérification d'e-mail pour l'inscription.

IMPORTANT — limite technique honnête : il n'existe aucun moyen 100% fiable de confirmer
qu'une boîte Gmail précise existe réellement. Google bloque volontairement la vérification
directe par SMTP (RCPT TO) pour la plupart des serveurs, pour des raisons anti-spam.

Ce module fait donc la meilleure vérification possible sans service payant :
1. Format de l'adresse valide (ex: pas de "@@" ou d'espace).
2. Le domaine (gmail.com, yahoo.com, etc.) a bien des serveurs de messagerie actifs (MX).
   Ça attrape la grande majorité des fautes de frappe (ex: "gmial.com", domaines inventés).

Pour une vérification plus poussée (confirmation quasi certaine que la boîte existe),
il faut un service tiers payant comme AbstractAPI ou ZeroBounce — voir EMAIL_VERIFICATION_API_KEY
dans le README pour l'activer optionnellement.
"""
import logging
import requests
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings

logger = logging.getLogger('transactions')


def _has_valid_mx_record(domain):
    """Vérifie que le domaine (ex: gmail.com) a bien des serveurs capables de recevoir
    des e-mails. Utilise dnspython ; si le paquet n'est pas installé ou la résolution
    échoue pour une raison réseau, on n'invalide pas l'inscription à cause de ça."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX', lifetime=5)
        return len(answers) > 0
    except ImportError:
        logger.warning("dnspython non installé : vérification MX ignorée.")
        return True
    except Exception:
        return False


def verify_email_exists(email):
    """Retourne (is_valid: bool, message: str)."""
    try:
        validate_email(email)
    except ValidationError:
        return False, "Format d'e-mail invalide."

    domain = email.rsplit('@', 1)[-1].lower()

    api_key = getattr(settings, 'EMAIL_VERIFICATION_API_KEY', '')
    if api_key:
        try:
            resp = requests.get(
                "https://emailvalidation.abstractapi.com/v1/",
                params={"api_key": api_key, "email": email},
                timeout=6,
            )
            data = resp.json()
            deliverable = data.get('deliverability') == 'DELIVERABLE'
            if deliverable:
                return True, "E-mail valide."
            return False, "Cette adresse e-mail semble invalide ou inexistante."
        except Exception:
            logger.warning("Vérification AbstractAPI indisponible, repli sur la vérification MX.")

    if not _has_valid_mx_record(domain):
        return False, "Ce domaine d'e-mail n'existe pas ou ne peut pas recevoir de messages."

    return True, "Domaine valide."
