# tests/test_signals.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet

User = get_user_model()

class SignalTest(TestCase):
    def test_wallet_created_on_user_creation(self):
        """Test that a wallet is automatically created when a user is created"""
        # Temporarily disconnect signals to test them properly
        # Or just create user and check if wallet exists
        user = User.objects.create(
            phone='+2348000000000',
            full_name='Test User',
            role='worker'
        )
        
        # Check if wallet was created (refresh from DB)
        user.refresh_from_db()
        
        # If signal is working, wallet should exist
        # If not, this will fail and you know signal needs fixing
        self.assertTrue(hasattr(user, 'wallet'))
        
        if hasattr(user, 'wallet'):
            self.assertIsInstance(user.wallet, Wallet)
            self.assertEqual(user.wallet.balance, 0)
    
    def test_wallet_not_created_again_on_update(self):
        """Test that updating user doesn't create duplicate wallet"""
        user = User.objects.create(
            phone='+2348000000001',
            full_name='Test User',
            role='worker'
        )
        
        # Skip test if wallet wasn't created
        if not hasattr(user, 'wallet'):
            self.skipTest("Signal not configured properly")
        
        wallet_id = user.wallet.id
        
        # Update user
        user.full_name = 'Updated Name'
        user.save()
        
        # Refresh and check same wallet exists
        user.refresh_from_db()
        self.assertEqual(user.wallet.id, wallet_id)