from django.urls import path
from . import views

app_name = 'wallets'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('historique/', views.history_view, name='history'),
    path('historique/<uuid:tx_id>/supprimer/', views.delete_transaction_view, name='delete_transaction'),
    path('convertir/', views.convert_view, name='convert'),
    path('retrait-crypto/', views.crypto_withdraw_view, name='crypto_withdraw'),
    path('actualiser-taux/', views.auto_update_rates_view, name='auto_update_rates'),
]
