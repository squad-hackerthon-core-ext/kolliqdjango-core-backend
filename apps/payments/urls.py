from django.urls import path
from . import views

urlpatterns = [
    path('transactions/', views.TransactionListView.as_view(), name='transaction-list'),
    path('webhook/squad/', views.SquadWebhookView.as_view(), name='squad-webhook'),
    path('webhook/internal/', views.InternalWebhookView.as_view(), name='internal-webhook'),
]