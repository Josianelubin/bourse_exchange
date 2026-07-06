from django.urls import path
from . import views

app_name = 'moncash'

urlpatterns = [
    path('depot/', views.deposit_view, name='deposit'),
    path('retour/', views.deposit_return_view, name='deposit_return'),
    path('retrait/', views.withdraw_view, name='withdraw'),
]
