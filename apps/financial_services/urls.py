from django.urls import path
from . import views

urlpatterns = [
    # Savings
    path('savings/', views.SavingsBalanceView.as_view(), name='savings-balance'),
    path('savings/deposit/', views.SavingsDepositView.as_view(), name='savings-deposit'),
    path('savings/withdraw/', views.SavingsWithdrawView.as_view(), name='savings-withdraw'),

    # Loans
    path('loans/', views.LoanListView.as_view(), name='loan-list'),
    path('loans/eligibility/', views.LoanEligibilityView.as_view(), name='loan-eligibility'),
    path('loans/apply/', views.LoanApplyView.as_view(), name='loan-apply'),
    path('loans/repay/', views.LoanRepayView.as_view(), name='loan-repay'),

    # Insurance
    path('insurance/', views.InsuranceStatusView.as_view(), name='insurance-status'),
    path('insurance/activate/', views.InsuranceActivateView.as_view(), name='insurance-activate'),
    path('insurance/claim/', views.InsuranceClaimView.as_view(), name='insurance-claim'),
    path('insurance/claims/', views.ClaimListView.as_view(), name='claim-list'),
]