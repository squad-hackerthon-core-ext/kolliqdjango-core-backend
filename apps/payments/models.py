from django.db import models
from django.conf import settings
import uuid
from decimal import Decimal
from apps.common.rls import UserOwnedModel


class Transaction(UserOwnedModel):

    class Type(models.TextChoices):
        CREDIT = 'credit', 'Credit'
        DEBIT = 'debit', 'Debit'
        ESCROW_HOLD = 'escrow_hold', 'Escrow Hold'
        ESCROW_RELEASE = 'escrow_release', 'Escrow Release'
        PLATFORM_FEE = 'platform_fee', 'Platform Fee'
        LOAN_DISBURSEMENT = 'loan_disbursement', 'Loan Disbursement'
        LOAN_REPAYMENT = 'loan_repayment', 'Loan Repayment'
        INSURANCE_PREMIUM = 'insurance_premium', 'Insurance Premium'
        INSURANCE_PAYOUT = 'insurance_payout', 'Insurance Payout'
        SAVINGS_DEPOSIT = 'savings_deposit', 'Savings Deposit'
        SAVINGS_WITHDRAWAL = 'savings_withdrawal', 'Savings Withdrawal'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        REVERSED = 'reversed', 'Reversed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=30, choices=Type.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # References
    squad_reference = models.CharField(max_length=200, blank=True)
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions'
    )
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='related_transactions'
    )

    # Metadata
    description = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transactions'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['squad_reference']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type} ₦{self.amount} — {self.user.phone} ({self.status})"

class ReconciliationReport(models.Model):
 
    class Status(models.TextChoices):
        OK       = 'ok',       'OK'
        CRITICAL = 'critical', 'Critical — Drift Detected'
        ERROR    = 'error',    'Error — Could Not Complete'
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
 
    status           = models.CharField(max_length=20, choices=Status.choices)
    expected_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    actual_balance   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    drift            = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    drift_percent    = models.DecimalField(max_digits=7,  decimal_places=4, null=True, blank=True)
 
    # Full breakdown of how expected was calculated
    breakdown        = models.JSONField(default=dict, blank=True)
 
    error_message    = models.TextField(blank=True, default='')
    ran_at           = models.DateTimeField()
    completed_at     = models.DateTimeField(null=True, blank=True)
 
    created_at       = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['-ran_at']
        verbose_name        = 'Reconciliation Report'
        verbose_name_plural = 'Reconciliation Reports'
 
    def __str__(self):
        drift_str = f'₦{self.drift:+,.2f}' if self.drift is not None else 'N/A'
        return f'[{self.status.upper()}] {self.ran_at:%Y-%m-%d %H:%M} | Drift: {drift_str}'
 
    @property
    def is_healthy(self):
        return self.status == self.Status.OK
 
    @property
    def drift_direction(self):
        if self.drift is None:
            return 'unknown'
        if self.drift > 0:
            return 'surplus'   # Squad has MORE than expected (unusual but ok)
        if self.drift < 0:
            return 'deficit'   # Squad has LESS than expected (dangerous)
        return 'balanced'
