"""
Row-Level Security (RLS) Implementation Guide

This guide explains how to use the row-level security system in your views,
viewsets, and serializers to ensure users can only access their own data.
"""

# ============================================================================
# 1. IN YOUR VIEWSETS/VIEWS - Using RLSPermissionMixin
# ============================================================================

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from apps.common.rls import RLSPermissionMixin
from apps.payments.models import Transaction
from apps.payments.serializers import TransactionSerializer


class TransactionViewSet(RLSPermissionMixin, ModelViewSet):
    """
    Transactions can only be viewed/edited by the user who owns them.
    
    The RLSPermissionMixin automatically:
    - Filters querysets to only show records accessible by the current user
    - Prevents access to records the user doesn't own
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        This will be automatically filtered by RLSPermissionMixin.
        Only transactions for the current user will be returned (unless admin).
        """
        return Transaction.objects.all()


# ============================================================================
# 2. IN YOUR SERIALIZERS - Using RLSSerializerMixin
# ============================================================================

from rest_framework import serializers
from apps.common.rls import RLSSerializerMixin
from apps.wallets.models import Wallet


class WalletSerializer(RLSSerializerMixin, serializers.ModelSerializer):
    """
    Ensures users can only update their own wallets.
    """
    class Meta:
        model = Wallet
        fields = ['id', 'user', 'balance', 'escrow_balance', 'savings_balance']
        read_only_fields = ['id', 'user', 'balance']


# ============================================================================
# 3. MODELS ALREADY HAVE RLS - How They Work
# ============================================================================

# UserOwnedModel adds:
# - .objects.for_user(user) - filter for specific user
# - .is_accessible_by(user) - check if user can access this record
# - Automatic admin bypass (staff/superuser can see all records)

from apps.payments.models import Transaction

# Usage in views:
def get_user_transactions(request):
    transactions = Transaction.objects.for_user(request.user)
    return transactions

# Check before returning a specific transaction:
def get_transaction_detail(request, tx_id):
    transaction = Transaction.objects.get(id=tx_id)
    if not transaction.is_accessible_by(request.user):
        raise PermissionDenied("You cannot access this transaction")
    return transaction


# ============================================================================
# 4. COMPLEX ACCESS RULES - UserOrganizedModel
# ============================================================================

# Models inheriting from UserOrganizedModel can define custom access rules
# by overriding can_access_record(). This is used for:
# - Jobs: Only employer can edit; workers can view open jobs
# - JobApplications: Worker and employer can view application
# - Ratings: Both rater and rated user can view

from apps.jobs.models import Job, JobApplication, Rating

# The model handles access logic:
job = Job.objects.get(id=job_id)
if job.can_access_record(request.user):
    # User has permission
    pass
else:
    raise PermissionDenied()


# ============================================================================
# 5. QUICK REFERENCE - Which Models Have RLS
# ============================================================================

"""
USER-OWNED MODELS (inherit from UserOwnedModel):
- Transaction (payments app)
- Wallet (wallets app)
- EconomicIdentityScore (scoring app)
- Loan (financial_services app)
- InsurancePolicy (financial_services app)
- InsuranceClaim (financial_services app)
- SavingsPot (financial_services app)

ORGANIZED MODELS (inherit from UserOrganizedModel with custom rules):
- Job (jobs app) - Employer owns; workers view open jobs
- JobApplication (jobs app) - Worker and employer can access
- Rating (jobs app) - Rater and rated user can access

SYSTEM MODELS (no RLS needed):
- DemoFloat (financial_services) - System wallet, not user-specific
- User (users) - Auth model
- Partner (partner) - System model
"""


# ============================================================================
# 6. TESTING RLS - Example Test Cases
# ============================================================================

from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.payments.models import Transaction

User = get_user_model()

class TransactionRLSTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(phone='2341234567890')
        self.user2 = User.objects.create_user(phone='2349876543210')
        
        self.tx1 = Transaction.objects.create(
            user=self.user1,
            transaction_type='credit',
            amount='1000.00'
        )
        self.tx2 = Transaction.objects.create(
            user=self.user2,
            transaction_type='credit',
            amount='2000.00'
        )
    
    def test_user_can_only_see_own_transactions(self):
        """User1 should only see their transactions"""
        user1_txs = Transaction.objects.for_user(self.user1)
        self.assertEqual(user1_txs.count(), 1)
        self.assertEqual(user1_txs.first(), self.tx1)
    
    def test_is_accessible_by_returns_false_for_other_user(self):
        """Transaction is not accessible to other users"""
        self.assertFalse(self.tx1.is_accessible_by(self.user2))
    
    def test_staff_can_see_all_transactions(self):
        """Admins bypass RLS"""
        admin = User.objects.create_user(
            phone='234admin123',
            is_staff=True
        )
        all_txs = Transaction.objects.for_user(admin)
        # Admin can see all transactions
        self.assertGreaterEqual(all_txs.count(), 2)


# ============================================================================
# 7. IMPORTANT NOTES & BEST PRACTICES
# ============================================================================

"""
✅ DO:
- Use RLSPermissionMixin in all viewsets that deal with user-owned data
- Use RLSSerializerMixin when you want to prevent unauthorized updates
- Always check is_accessible_by() before returning records in custom views
- Test RLS with multiple users to ensure data isolation

❌ DON'T:
- Bypass RLS by using raw SQL queries without filtering
- Return all records without filtering by user
- Trust client-submitted user IDs without verifying ownership
- Use select_related/prefetch_related without filtering related objects

⚡ PERFORMANCE:
- The for_user() method uses indexed queries (user_id is indexed)
- RLS filters are applied at the database level, not in Python
- Admin bypass (is_staff/is_superuser) is checked in Python to avoid
  unnecessary database queries for staff users
"""
