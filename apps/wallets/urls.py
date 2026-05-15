from django.urls import path
from . import views
from apps.wallets.views import (
    BankAccountDetailView,
    BankAccountVerifyView,
    BankAccountSaveView,
    NigerianBankListView,
    WithdrawalRequestView,

)


urlpatterns = [
    path('', views.WalletDetailView.as_view(), name='wallet-detail'),
    path('banks/',                NigerianBankListView.as_view(),  name='bank-list'),
 
    # Authenticated
    path('bank-account/',         BankAccountDetailView.as_view(), name='bank-account-detail'),
    path('bank-account/verify/',  BankAccountVerifyView.as_view(), name='bank-account-verify'),
    path('bank-account/save/',    BankAccountSaveView.as_view(),   name='bank-account-save'),

    path('withdraw/', WithdrawalRequestView.as_view(), name='wallet-withdraw'),
]
