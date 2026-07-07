from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


_CRYPTO_LOGOS = {
    'USDTTRC20': 'usdt.png',
    'TRX': 'trx.png',
    'BTC': 'bitcoin.png',
    'ETH': 'etherum.png',
    'MATIC': 'Matic.png',
    'SOL': 'sol.png',
}

@register.filter
def crypto_logo(symbol):
    """Retourne le chemin du logo local correspondant à cette devise."""
    filename = _CRYPTO_LOGOS.get(symbol, 'usdt.png')
    return f"/static/img/{filename}"
