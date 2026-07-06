from decimal import Decimal
from django import forms
from accounts.forms import StyledFormMixin
from .models import CryptoCurrency


class MonCashDepositForm(StyledFormMixin, forms.Form):
    amount = forms.DecimalField(min_value=Decimal('50'), max_digits=20, decimal_places=2, label="Montant (HTG)")


class MonCashWithdrawForm(StyledFormMixin, forms.Form):
    amount = forms.DecimalField(min_value=Decimal('1000'), max_digits=20, decimal_places=2,
                                 label="Montant (HTG) — minimum 1000 HTG")
    moncash_phone = forms.CharField(max_length=20, label="Numéro MonCash")


class CryptoWithdrawForm(StyledFormMixin, forms.Form):
    currency = forms.ModelChoiceField(queryset=CryptoCurrency.objects.filter(is_active=True))
    amount = forms.DecimalField(min_value=Decimal('0.000001'), max_digits=30, decimal_places=8)
    destination_address = forms.CharField(max_length=255, label="Adresse de destination")


class ConvertForm(StyledFormMixin, forms.Form):
    pay_currency = forms.ChoiceField(label="Vous payez avec")
    receive_currency = forms.ChoiceField(label="Vous recevez en")
    amount = forms.DecimalField(min_value=Decimal('0.00000001'), max_digits=30, decimal_places=8,
                                 label="Quantité à payer")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        currencies = list(CryptoCurrency.objects.filter(is_active=True))
        choices = [('HTG', 'HTG')] + [(c.symbol, c.symbol) for c in currencies]
        self.fields['pay_currency'].choices = choices
        self.fields['receive_currency'].choices = choices
        if not self.is_bound:
            self.fields['pay_currency'].initial = 'HTG'
            if currencies:
                self.fields['receive_currency'].initial = currencies[0].symbol

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('pay_currency') and cleaned.get('pay_currency') == cleaned.get('receive_currency'):
            raise forms.ValidationError("La devise payée et la devise reçue doivent être différentes.")
        return cleaned
