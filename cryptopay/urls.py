from django.urls import path
from . import views

app_name = 'cryptopay'

urlpatterns = [
    path('depot/', views.deposit_address_view, name='deposit_address'),
    path('depot/generer/<int:currency_id>/', views.generate_address_view, name='generate_address'),
    path('webhook/nowpayments/', views.nowpayments_webhook, name='nowpayments_webhook'),
]
