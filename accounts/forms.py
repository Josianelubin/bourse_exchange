from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, IdentityVerification


class StyledFormMixin:
    """Applique automatiquement les classes Bootstrap (form-control / form-select /
    form-check-input) à TOUS les champs d'un formulaire. Sans ça, Django génère des
    <input> et <select> bruts, sans aucune classe CSS — ils ignorent alors entièrement
    le thème du site et gardent le blanc par défaut du navigateur."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = 'form-select'
            else:
                css = 'form-control'
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = f"{existing} {css}".strip()


class RegisterForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(required=False, max_length=20)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'phone_number', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée.")
        from .services import verify_email_exists
        is_valid, message = verify_email_exists(email)
        if not is_valid:
            raise forms.ValidationError(message)
        return email


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone_number']


class DeleteAccountForm(StyledFormMixin, forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label="Confirmez avec votre mot de passe")
    confirmation = forms.CharField(
        label='Tapez "SUPPRIMER" pour confirmer',
        widget=forms.TextInput(attrs={'placeholder': 'SUPPRIMER'})
    )

    def clean_confirmation(self):
        value = self.cleaned_data['confirmation']
        if value.strip().upper() != 'SUPPRIMER':
            raise forms.ValidationError('Veuillez taper exactement "SUPPRIMER".')
        return value


class IdentityVerificationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = IdentityVerification
        fields = ['id_document_front', 'id_document_back', 'selfie']
        widgets = {
            # Pas d'attribut "capture" : le navigateur propose alors les DEUX options
            # (choisir un fichier existant OU prendre une photo avec l'appareil photo).
            'id_document_front': forms.FileInput(attrs={'accept': 'image/*'}),
            'id_document_back': forms.FileInput(attrs={'accept': 'image/*'}),
            'selfie': forms.FileInput(attrs={'accept': 'image/*'}),
        }
