from django.db import models
from django.conf import settings
import uuid
from decimal import Decimal
from apps.common.rls import UserOwnedModel


class Wallet(UserOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet'
    )

    # Squad virtual account details
    squad_account_number = models.CharField(max_length=20, blank=True)
    squad_account_name = models.CharField(max_length=200, blank=True)
    squad_bank_name = models.CharField(max_length=100, blank=True, default='Squad MFB')
    squad_customer_id = models.CharField(max_length=100, blank=True)
    squad_virtual_account_ref = models.CharField(max_length=200, blank=True, unique=True, null=True)

    # Balances
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    escrow_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    savings_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # Bank account details
    bank_account_number = models.CharField(max_length=10, blank=True)
    bank_code = models.CharField(max_length=10, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)
    bank_account_verified = models.BooleanField(default=False)
    bank_account_updated_at = models.DateTimeField(blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)
    squad_creation_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('created', 'Created'), ('failed', 'Failed')],
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallets'

    def __str__(self):
        return f"Wallet({self.user.phone}) — ₦{self.balance}"

    def credit(self, amount, save=True):
        self.balance += Decimal(str(amount))
        if save:
            self.save(update_fields=['balance', 'updated_at'])

    def debit(self, amount, save=True):
        if self.balance < Decimal(str(amount)):
            raise ValueError('Insufficient wallet balance')
        self.balance -= Decimal(str(amount))
        if save:
            self.save(update_fields=['balance', 'updated_at'])

class WithdrawalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, on_delete=models.PROTECT, related_name='withdrawals'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Snapshot bank details at time of request (in case user changes bank later)
    bank_account_number = models.CharField(max_length=10)
    bank_code = models.CharField(max_length=10)
    bank_name = models.CharField(max_length=100)
    bank_account_name = models.CharField(max_length=150)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    squad_reference = models.CharField(max_length=200, blank=True)
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_withdrawals'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'withdrawal_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal ₦{self.amount} — {self.wallet.user.phone} [{self.status}]"