# tests/test_financial_views.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from apps.wallets.models import Wallet
from apps.scoring.models import EconomicIdentityScore

User = get_user_model()

class FinancialServiceViewTest(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create(
            phone='+2348000000006',
            full_name='Test User',
            role='worker'
        )
        
        # Manually create wallet (since signal might not be working)
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('100000.00'),
            escrow_balance=Decimal('0.00')
        )
        
        # Create a score for the user (low score for insufficient tests)
        self.score = EconomicIdentityScore.objects.create(
            user=self.user,
            score=30,  # Low score - below loan threshold (50)
            savings_unlocked=False,
            insurance_unlocked=False,
            loan_unlocked=False
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_loan_application_with_insufficient_score(self):
        response = self.client.post('/api/financial/apply-loan/', {
            'amount': '50000.00',
            'purpose': 'Business expansion'
        }, format='json')
        
        # Should fail because score < 50
        self.assertEqual(response.status_code, 400)
    
    def test_loan_application_with_missing_fields(self):
        response = self.client.post('/api/financial/apply-loan/', {
            'amount': '50000.00'
            # Missing purpose
        }, format='json')
        self.assertEqual(response.status_code, 400)
    
    def test_insurance_activation_with_insufficient_score(self):
        response = self.client.post('/api/financial/activate-insurance/', {
            'daily_premium': '200.00'
        }, format='json')
        
        # Should fail because score < 70
        self.assertEqual(response.status_code, 400)
    
    def test_savings_contribution_with_negative_amount(self):
        response = self.client.post('/api/financial/savings/deposit/', {
            'amount': '-5000.00'
        }, format='json')
        self.assertEqual(response.status_code, 400)
    
    def test_get_loan_eligibility(self):
        response = self.client.get('/api/financial/loan-eligibility/')
        self.assertEqual(response.status_code, 200)
        data = response.json().get('data', {})
        self.assertIn('eligible', data)
        self.assertIn('max_amount', data)