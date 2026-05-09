from django.contrib import admin
from .models import Loan, InsurancePolicy, InsuranceClaim, SavingsPot, DemoFloat


@admin.register(DemoFloat)
class DemoFloatAdmin(admin.ModelAdmin):
    list_display = ['balance', 'total_disbursed', 'total_repaid', 'updated_at']
    readonly_fields = ['id', 'total_disbursed', 'total_repaid', 'updated_at']


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'amount', 'total_repayable', 'amount_repaid',
        'outstanding_balance', 'status', 'funding_source',
        'disbursed_at', 'due_date'
    ]
    list_filter = ['status', 'funding_source']
    search_fields = ['user__phone', 'user__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'outstanding_balance']
    ordering = ['-created_at']

    def outstanding_balance(self, obj):
        return f'₦{obj.outstanding_balance}'


@admin.register(InsurancePolicy)
class InsurancePolicyAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'daily_premium', 'coverage_limit',
        'days_active', 'total_premiums_paid', 'status', 'activated_at'
    ]
    list_filter = ['status']
    search_fields = ['user__phone']
    readonly_fields = ['id', 'created_at']


@admin.register(InsuranceClaim)
class InsuranceClaimAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'days_missed', 'payout_amount', 'status',
        'funding_source', 'paid_at', 'created_at'
    ]
    list_filter = ['status', 'funding_source']
    search_fields = ['user__phone']
    readonly_fields = ['id', 'created_at', 'updated_at']
    # Admin can approve manual review claims here
    actions = ['approve_claims']

    def approve_claims(self, request, queryset):
        from decimal import Decimal
        from apps.payments.models import Transaction
        from django.utils import timezone
        from .models import DemoFloat

        for claim in queryset.filter(status='manual_review'):
            try:
                demo_float = DemoFloat.objects.get(id=1)
                demo_float.disburse(claim.payout_amount)
                claim.user.wallet.credit(claim.payout_amount)
                claim.status = InsuranceClaim.Status.PAID
                claim.paid_at = timezone.now()
                claim.admin_notes = f'Approved by admin {request.user}'
                claim.save()
                Transaction.objects.create(
                    user=claim.user,
                    transaction_type=Transaction.Type.INSURANCE_PAYOUT,
                    amount=claim.payout_amount,
                    status=Transaction.Status.SUCCESS,
                    description='Insurance claim approved by admin',
                    metadata={'claim_id': str(claim.id), 'source': 'demo_float'},
                )
            except Exception as e:
                self.message_user(request, f"Failed for {claim.user.phone}: {e}")

    approve_claims.short_description = "Approve selected claims and disburse payout"


@admin.register(SavingsPot)
class SavingsPotAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'total_deposited', 'total_interest_earned', 'updated_at']
    search_fields = ['user__phone']
    readonly_fields = ['id', 'created_at']