"""
Mise à jour automatique des prix HTG <-> USDT <-> TRX.

Deux appels sont nécessaires car aucune API ne donne directement "1 USDT = combien de HTG" :
1. CoinGecko (gratuit, sans clé) donne le prix des cryptos en USD.
2. Une API de taux de change fiat (ExchangeRate-API, clé gratuite) donne 1 USD = combien de HTG.

On combine les deux : prix_HTG(crypto) = prix_USD(crypto) x taux(USD -> HTG).
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger('transactions')

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
EXCHANGE_RATE_URL = "https://v6.exchangerate-api.com/v6/{key}/latest/USD"


def fetch_usd_to_htg_rate():
    """1 USD = combien de HTG, via ExchangeRate-API (clé gratuite requise)."""
    api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', '')
    if not api_key:
        raise RuntimeError(
            "EXCHANGE_RATE_API_KEY non configurée — ajoute cette variable d'environnement "
            "avec une clé gratuite obtenue sur https://www.exchangerate-api.com/"
        )
    resp = requests.get(EXCHANGE_RATE_URL.format(key=api_key), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    rate = data.get('conversion_rates', {}).get('HTG')
    if not rate:
        raise RuntimeError("Taux HTG introuvable dans la réponse ExchangeRate-API.")
    return Decimal(str(rate))


def fetch_crypto_usd_prices(coingecko_ids):
    """Retourne {'tether': Decimal(...), 'tron': Decimal(...)} en dollars US.
    CoinGecko exige maintenant une clé (gratuite) même sur le plan Demo."""
    params = {"ids": ",".join(coingecko_ids), "vs_currencies": "usd"}
    api_key = getattr(settings, 'COINGECKO_API_KEY', '')
    if api_key:
        params["x_cg_demo_api_key"] = api_key
    resp = requests.get(COINGECKO_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return {k: Decimal(str(v['usd'])) for k, v in data.items() if 'usd' in v}


def update_all_htg_rates():
    """Met à jour htg_exchange_rate pour toutes les cryptos actives à partir des prix
    réels du marché. Retourne un résumé texte des changements effectués (pour affichage
    dans l'admin)."""
    from wallets.models import CryptoCurrency

    mapping = {
        'USDTTRC20': 'tether', 'TRX': 'tron',
        'BTC': 'bitcoin', 'ETH': 'ethereum', 'MATIC': 'matic-network', 'SOL': 'solana',
    }
    usd_to_htg = fetch_usd_to_htg_rate()
    prices_usd = fetch_crypto_usd_prices(list(mapping.values()))

    results = []
    for symbol, coingecko_id in mapping.items():
        if coingecko_id not in prices_usd:
            continue
        try:
            currency = CryptoCurrency.objects.get(symbol=symbol)
        except CryptoCurrency.DoesNotExist:
            continue
        new_rate = (prices_usd[coingecko_id] * usd_to_htg).quantize(Decimal('0.0001'))
        old_rate = currency.htg_exchange_rate
        currency.htg_exchange_rate = new_rate
        currency.save(update_fields=['htg_exchange_rate'])
        results.append(f"{symbol}: {old_rate} → {new_rate} HTG")

    return results
