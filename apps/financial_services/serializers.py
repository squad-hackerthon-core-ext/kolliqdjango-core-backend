from rest_framework import serializers
from decimal import Decimal
from .models import Loan, InsurancePolicy, InsuranceClaim, SavingsPot, DemoFloat


class LoanEligibilitySerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = serializers.FloatField()
    tenure_days = serializers.IntegerField()
    funding_source = serializers.CharField()
    note = serializers.CharField()
    reason = serializers.CharField(allow_blank=True)


class LoanApplySerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('500'))

    def validate_amount(self, value):
        user = self.context.get('user') or self.context['request'].user
        # Check against active loan
        if user.loans.filter(status__in=['pending', 'active', 'partially_repaid']).exists():
            raise serializers.ValidationError('You already have an active loan.')
        return value


class LoanSerializer(serializers.ModelSerializer):
    outstanding_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    next_repayment = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            'id', 'amount', 'interest_rate_monthly', 'total_repayable',
            'amount_repaid', 'outstanding_balance', 'status',
            'funding_source', 'repayment_schedule', 'next_repayment',
            'disbursed_at', 'due_date', 'created_at',
        ]

    def get_next_repayment(self, obj):
        for installment in obj.repayment_schedule:
            if not installment.get('paid'):
                return installment
        return None


class LoanRepaySerializer(serializers.Serializer):
    loan_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1'))


class InsurancePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = InsurancePolicy
        fields = [
            'id', 'daily_premium', 'coverage_limit', 'days_active',
            'total_premiums_paid', 'status', 'funding_source',
            'activated_at', 'created_at',
        ]


class InsuranceClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceClaim
        fields = [
            'id', 'days_missed', 'reason', 'payout_amount',
            'status', 'funding_source', 'admin_notes', 'paid_at', 'created_at',
        ]


class InsuranceClaimCreateSerializer(serializers.Serializer):
    days_missed = serializers.IntegerField(min_value=1, max_value=30)
    reason = serializers.CharField(max_length=1000)


class SavingsPotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsPot
        fields = [
            'id', 'balance', 'total_deposited',
            'total_interest_earned', 'target_amount',
            'created_at', 'updated_at',
        ]


class SavingsDepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('100'))


class SavingsWithdrawSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('100'))