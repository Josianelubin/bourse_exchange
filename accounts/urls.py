from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('inscription/', views.register_view, name='register'),
    path('verifier-email-existe/', views.check_email_view, name='check_email'),
    path('verifier-email/<uuid:token>/', views.verify_email_view, name='verify_email'),
    path('connexion/', views.login_view, name='login'),
    path('deconnexion/', views.logout_view, name='logout'),
    path('profil/', views.profile_view, name='profile'),
    path('parametres/', views.settings_view, name='settings'),
    path('verification-identite/', views.kyc_upload_view, name='kyc_upload'),
    path('supprimer-compte/', views.delete_account_view, name='delete_account'),
    path('mot-de-passe/reinitialiser/', views.password_reset_view, name='password_reset'),
    path('mot-de-passe/reinitialiser/termine/',
         auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
         name='password_reset_done'),
    path('mot-de-passe/reinitialiser/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url=reverse_lazy('accounts:password_reset_complete'),
         ),
         name='password_reset_confirm'),
    path('mot-de-passe/reinitialiser/complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
         name='password_reset_complete'),
]
