from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.db import transaction as db_transaction
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from datetime import date, timedelta
import uuid
import logging

from kolliq.utils import success_response, error_response
from .models import Loan, InsurancePolicy, InsuranceClaim, SavingsPot, DemoFloat
from .serializers import (
    LoanEligibilitySerializer, LoanApplySerializer, LoanSerializer,
    LoanRepaySerializer, InsurancePolicySerializer, InsuranceClaimSerializer,
    InsuranceClaimCreateSerializer, SavingsPotSerializer,
    SavingsDepositSerializer, SavingsWithdrawSerializer,
)

logger = logging.getLogger(__name__)

AUTO_APPROVE_THRESHOLD = Decimal('5000.00')


# ══════════════════════════════════════════════════════════════════
# SAVINGS
# ══════════════════════════════════════════════════════════════════

class SavingsBalanceView(APIView):
    """GET /api/financial/savings/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='savings_balance',
        summary='Get savings balance',
        description='Retrieve current savings balance and eligibility status',
        tags=['Financial Services'],
    )
    def get(self, request):
        user = request.user
        try:
            score = user.economic_score.score
        except Exception:
            score = 0

        if score < settings.SAVINGS_SCORE_THRESHOLD:
            return success_response({
                'unlocked': False,
                'score': score,
                'score_needed': settings.SAVINGS_SCORE_THRESHOLD,
                'message': f"Complete more gigs to unlock savings. Need score {settings.SAVINGS_SCORE_THRESHOLD}.",
            })

        pot, _ = SavingsPot.objects.get_or_create(user=user)
        wallet_balance = str(user.wallet.balance) if hasattr(user, 'wallet') else '0.00'

        return success_response({
            'unlocked': True,
            'wallet_balance': wallet_balance,
            'savings': SavingsPotSerializer(pot).data,
            'annual_interest_rate': settings.SAVINGS_ANNUAL_INTEREST_RATE,
        })


class SavingsDepositView(APIView):
    """POST /api/financial/savings/deposit/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='savings_deposit',
        summary='Deposit to savings',
        description='Move funds from wallet to savings',
        request=SavingsDepositSerializer,
        tags=['Financial Services'],
    )
    def post(self, request):
        user = request.user
        serializer = SavingsDepositSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        amount = serializer.validated_data['amount']

        try:
            score = user.economic_score.score
        except Exception:
            score = 0

        if score < settings.SAVINGS_SCORE_THRESHOLD:
            return error_response(
                f'Savings unlocks at score {settings.SAVINGS_SCORE_THRESHOLD}. '
                f'Your score: {score}.',
                status=403
            )

        with db_transaction.atomic():
            wallet = user.wallet
            try:
                wallet.debit(amount)
            except ValueError as e:
                return error_response(str(e), status=400)

            pot, _ = SavingsPot.objects.get_or_create(user=user)
            pot.balance += amount
            pot.total_deposited += amount
            pot.save(update_fields=['balance', 'total_deposited', 'updated_at'])

            from apps.payments.models import Transaction
            Transaction.objects.create(
                user=user,
                transaction_type=Transaction.Type.SAVINGS_DEPOSIT,
                amount=amount,
                status=Transaction.Status.SUCCESS,
                description='Savings deposit',
            )

        return success_response({
            'deposited': str(amount),
            'savings_balance': str(pot.balance),
            'wallet_balance': str(wallet.balance),
            'message': f'₦{amount} moved to savings. Earning {settings.SAVINGS_ANNUAL_INTEREST_RATE}% p.a.',
        })


class SavingsWithdrawView(APIView):
    """POST /api/financial/savings/withdraw/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='savings_withdraw',
        summary='Withdraw from savings',
        description='Transfer funds from savings to wallet',
        request=SavingsWithdrawSerializer,
        tags=['Financial Services'],
    )
    def post(self, request):
        user = request.user
        serializer = SavingsWithdrawSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        amount = serializer.validated_data['amount']

        with db_transaction.atomic():
            try:
                pot = user.savings_pot
            except SavingsPot.DoesNotExist:
                return error_response('No savings pot found.', status=404)

            if pot.balance < amount:
                return error_response(
                    f'Insufficient savings. Balance: ₦{pot.balance}',
                    status=400
                )

            pot.balance -= amount
            pot.save(update_fields=['balance', 'updated_at'])

            wallet = user.wallet
            wallet.credit(amount)

            from apps.payments.models import Transaction
            Transaction.objects.create(
                user=user,
                transaction_type=Transaction.Type.SAVINGS_WITHDRAWAL,
                amount=amount,
                status=Transaction.Status.SUCCESS,
                description='Savings withdrawal',
            )

        return success_response({
            'withdrawn': str(amount),
            'savings_balance': str(pot.balance),
            'wallet_balance': str(wallet.balance),
        })


# ══════════════════════════════════════════════════════════════════
# LOANS
# ══════════════════════════════════════════════════════════════════

def _get_max_loan_amount(score: int) -> Decimal:
    if score < 50:   return Decimal('0')
    if score < 60:   return Decimal('10000')
    if score < 75:   return Decimal('25000')
    if score < 90:   return Decimal('50000')
    return Decimal('100000')


def _build_repayment_schedule(principal: Decimal, total: Decimal, disbursed_date) -> list:
    """4 weekly installments."""
    weekly = (total / 4).quantize(Decimal('0.01'))
    schedule = []
    for i in range(1, 5):
        due = disbursed_date + timedelta(weeks=i)
        schedule.append({
            'week': i,
            'due_date': due.strftime('%Y-%m-%d'),
            'amount': str(weekly),
            'paid': False,
            'paid_at': None,
        })
    return schedule


class LoanEligibilityView(APIView):
    """GET /api/financial/loans/eligibility/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='loan_eligibility',
        summary='Check loan eligibility',
        description='Check if eligible for loans and max loan amount',
        tags=['Financial Services'],
    )
    def get(self, request):
        user = request.user

        try:
            score = user.economic_score.score
        except Exception:
            score = 0

        # Check for active loan
        has_active_loan = user.loans.filter(
            status__in=['pending', 'active', 'partially_repaid']
        ).exists()

        if has_active_loan:
            active_loan = user.loans.filter(
                status__in=['pending', 'active', 'partially_repaid']
            ).first()
            return success_response({
                'eligible': False,
                'reason': 'You have an active loan. Repay it first.',
                'active_loan': LoanSerializer(active_loan).data,
                'max_amount': '0',
                'funding_source': 'demo_float',
                'note': '',
            })

        max_amount = _get_max_loan_amount(score)
        eligible = score >= settings.LOAN_SCORE_THRESHOLD and max_amount > 0

        return success_response({
            'eligible': eligible,
            'score': score,
            'score_needed': settings.LOAN_SCORE_THRESHOLD,
            'max_amount': str(max_amount),
            'interest_rate': settings.LOAN_INTEREST_RATE_MONTHLY,
            'tenure_days': 28,
            'funding_source': 'demo_float',
            'financial_partner_mode': settings.FINANCIAL_PARTNER_MODE,
            'note': (
                'Pre-qualified based on your verified economic activity. '
                'Funds disbursed from Kolliq demo float. '
                'A microfinance partner will provide capital at scale.'
            ) if eligible else '',
            'reason': (
                f'Score too low. Need {settings.LOAN_SCORE_THRESHOLD}, have {score}.'
            ) if not eligible else '',
        })


class LoanApplyView(APIView):
    """POST /api/financial/loans/apply/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='loan_apply',
        summary='Apply for loan',
        description='Submit loan application and receive disbursement',
        request=LoanApplySerializer,
        tags=['Financial Services'],
    )
    def post(self, request):
        user = request.user
        serializer = LoanApplySerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return error_response(serializer.errors)

        amount = serializer.validated_data['amount']

        try:
            score = user.economic_score.score
        except Exception:
            score = 0

        max_amount = _get_max_loan_amount(score)

        if score < settings.LOAN_SCORE_THRESHOLD:
            return error_response(
                f'Score too low. Need {settings.LOAN_SCORE_THRESHOLD}, have {score}.',
                status=403
            )

        if amount > max_amount:
            return error_response(
                f'Amount exceeds your limit of ₦{max_amount}. '
                f'Complete more gigs to increase your limit.',
                status=400
            )

        interest_rate = Decimal(str(settings.LOAN_INTEREST_RATE_MONTHLY)) / 100
        total_repayable = (amount * (1 + interest_rate)).quantize(Decimal('0.01'))
        now = timezone.now()

        with db_transaction.atomic():
            # Debit demo float
            try:
                demo_float = DemoFloat.objects.select_for_update().get(id=1)
            except DemoFloat.DoesNotExist:
                return error_response(
                    'Loan facility temporarily unavailable. Try again shortly.',
                    status=503
                )

            try:
                demo_float.disburse(amount)
            except ValueError as e:
                logger.error(f"Demo float insufficient for loan: {e}")
                return error_response(
                    'Loan facility at capacity. Please try again tomorrow.',
                    status=503
                )

            schedule = _build_repayment_schedule(amount, total_repayable, now.date())

            loan = Loan.objects.create(
                user=user,
                amount=amount,
                interest_rate_monthly=settings.LOAN_INTEREST_RATE_MONTHLY,
                total_repayable=total_repayable,
                status=Loan.Status.ACTIVE,
                repayment_schedule=schedule,
                disbursed_at=now,
                due_date=now.date() + timedelta(days=28),
                funding_source='demo_float',
                squad_disbursement_ref=f"loan-disburse-{uuid.uuid4().hex[:12]}",
            )

            # Credit user wallet
            user.wallet.credit(amount)

            # Record transaction
            from apps.payments.models import Transaction
            Transaction.objects.create(
                user=user,
                transaction_type=Transaction.Type.LOAN_DISBURSEMENT,
                amount=amount,
                status=Transaction.Status.SUCCESS,
                description=f'Loan disbursed — ₦{amount} at {settings.LOAN_INTEREST_RATE_MONTHLY}%/month',
                metadata={
                    'loan_id': str(loan.id),
                    'source': 'demo_float',
                    'total_repayable': str(total_repayable),
                }
            )

        # Async notifications
        from services.notifications import notify_loan_disbursed
        first_due = schedule[0]['due_date']
        notify_loan_disbursed.delay(str(user.id), str(amount), first_due)

        from apps.scoring.tasks import recalculate_score
        recalculate_score.delay(str(user.id))

        return success_response({
            'loan_id': str(loan.id),
            'amount_disbursed': str(amount),
            'total_repayable': str(total_repayable),
            'interest_rate_monthly': settings.LOAN_INTEREST_RATE_MONTHLY,
            'repayment_schedule': schedule,
            'wallet_balance': str(user.wallet.balance),
            'funding_source': 'demo_float',
            'message': (
                f'₦{amount} disbursed to your wallet. '
                f'Total to repay: ₦{total_repayable} in 4 weekly installments.'
            ),
        }, status=201)


class LoanRepayView(APIView):
    """POST /api/financial/loans/repay/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='loan_repay',
        summary='Repay loan',
        description='Make loan repayment',
        request=LoanRepaySerializer,
        tags=['Financial Services'],
    )
    def post(self, request):
        user = request.user
        serializer = LoanRepaySerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        loan_id = serializer.validated_data['loan_id']
        amount = serializer.validated_data['amount']

        try:
            loan = Loan.objects.get(id=loan_id, user=user)
        except Loan.DoesNotExist:
            return error_response('Loan not found.', status=404)

        if loan.status not in ['active', 'partially_repaid']:
            return error_response(f'Loan is not active (status: {loan.status}).', status=400)

        if amount > loan.outstanding_balance:
            amount = loan.outstanding_balance  # Accept over-payment gracefully

        with db_transaction.atomic():
            # Debit user wallet
            try:
                user.wallet.debit(amount)
            except ValueError as e:
                return error_response(str(e), status=400)

            # Update loan
            loan.amount_repaid += amount
            if loan.amount_repaid >= loan.total_repayable:
                loan.status = Loan.Status.REPAID
            else:
                loan.status = Loan.Status.PARTIALLY_REPAID

            # Mark installments paid in schedule
            remaining = amount
            for installment in loan.repayment_schedule:
                if not installment['paid'] and remaining > 0:
                    inst_amount = Decimal(installment['amount'])
                    if remaining >= inst_amount:
                        installment['paid'] = True
                        installment['paid_at'] = timezone.now().isoformat()
                        remaining -= inst_amount
                    else:
                        # Partial installment payment — mark partial
                        installment['partial_paid'] = str(remaining)
                        remaining = Decimal('0')

            loan.save(update_fields=['amount_repaid', 'status', 'repayment_schedule', 'updated_at'])

            # Return to demo float
            try:
                demo_float = DemoFloat.objects.select_for_update().get(id=1)
                demo_float.receive_repayment(amount)
            except DemoFloat.DoesNotExist:
                pass

            # Transaction record
            from apps.payments.models import Transaction
            Transaction.objects.create(
                user=user,
                transaction_type=Transaction.Type.LOAN_REPAYMENT,
                amount=amount,
                status=Transaction.Status.SUCCESS,
                description=f'Loan repayment — outstanding: ₦{loan.outstanding_balance}',
                metadata={'loan_id': str(loan.id), 'source': 'demo_float'},
            )

        # Score recalculation — repayment is a positive score event
        from apps.scoring.tasks import recalculate_score
        recalculate_score.delay(str(user.id))

        return success_response({
            'repaid': str(amount),
            'outstanding_balance': str(loan.outstanding_balance),
            'loan_status': loan.status,
            'wallet_balance': str(user.wallet.balance),
            'message': (
                'Loan fully repaid! Your score has increased and your next loan limit is higher.'
                if loan.status == Loan.Status.REPAID
                else f'₦{amount} repaid. Outstanding: ₦{loan.outstanding_balance}.'
            ),
        })


class LoanListView(APIView):
    """GET /api/financial/loans/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='loans_list',
        summary='List loans',
        description='Get all loans for current user',
        tags=['Financial Services'],
    )
    def get(self, request):
        loans = request.user.loans.all().order_by('-created_at')
        return success_response({
            'loans': LoanSerializer(loans, many=True).data,
            'count': loans.count(),
        })


# ══════════════════════════════════════════════════════════════════
# INSURANCE
# ══════════════════════════════════════════════════════════════════

class InsuranceActivateView(APIView):
    """POST /api/financial/insurance/activate/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='insurance_activate',
        summary='Activate insurance',
        description='Activate insurance policy',
        tags=['Financial Services'],
    )
    def post(self, request):
        user = request.user

        try:
            score = user.economic_score.score
        except Exception:
            score = 0

        if score < settings.INSURANCE_SCORE_THRESHOLD:
            return error_response(
                f'Insurance unlocks at score {settings.INSURANCE_SCORE_THRESHOLD}. '
                f'Your score: {score}.',
                status=403
            )

        # Check no active policy
        active = user.insurance_policies.filter(status='active').first()
        if active:
            return success_response({
                'already_active': True,
                'policy': InsurancePolicySerializer(active).data,
                'message': 'You already have an active insurance policy.',
            })

        daily_premium = Decimal(str(settings.INSURANCE_DAILY_PREMIUM))

        # Check wallet can afford first premium
        try:
            wallet_balance = user.wallet.balance
        except Exception:
            wallet_balance = Decimal('0')

        if wallet_balance < daily_premium:
            return error_response(
                f'Insufficient wallet balance for first premium. '
                f'Need ₦{daily_premium}, have ₦{wallet_balance}.',
                status=400
            )

        with db_transaction.atomic():
            # Deduct first day premium immediately
            user.wallet.debit(daily_premium)

            policy = InsurancePolicy.objects.create(
                user=user,
                daily_premium=daily_premium,
                coverage_limit=settings.INSURANCE_COVERAGE_LIMIT,
                days_active=1,
                total_premiums_paid=daily_premium,
                funding_source='demo_float',
            )

            from apps.payments.models import Transaction
            Transaction.objects.create(
                user=user,
                transaction_type=Transaction.Type.INSURANCE_PREMIUM,
                amount=daily_premium,
                status=Transaction.Status.SUCCESS,
                description='Insurance activated — Day 1 premium',
                metadata={'policy_id': str(policy.id), 'source': 'demo_float'},
            )

        from apps.scoring.tasks import recalculate_score
        recalculate_score.delay(str(user.id))

        return success_response({
            'policy_id': str(policy.id),
            'daily_premium': str(daily_premium),
            'coverage_limit': str(policy.coverage_limit),
            'status': policy.status,
            'funding_source': 'demo_float',
            'message': (
                f'Insurance activated! ₦{daily_premium} deducted daily. '
                f'Coverage: up to ₦{policy.coverage_limit} for theft, fire, or missed work days.'
            ),
        }, status=201)


class InsuranceStatusView(APIView):
    """GET /api/financial/insurance/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='insurance_status',
        summary='Get insurance status',
        description='Get current insurance policy status',
        tags=['Financial Services'],
    )
    def get(self, request):
        policies = request.user.insurance_policies.all().order_by('-activated_at')
        active = policies.filter(status='active').first()
        return success_response({
            'has_active_policy': active is not None,
            'active_policy': InsurancePolicySerializer(active).data if active else None,
            'all_policies': InsurancePolicySerializer(policies, many=True).data,
        })


class InsuranceClaimView(APIView):
    """POST /api/financial/insurance/claim/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='insurance_claim',
        summary='Submit insurance claim',
        description='Submit claim for insurance payout',
        request=InsuranceClaimCreateSerializer,
        tags=['Financial Services'],
    )
    def post(self, request):
        user = request.user
        serializer = InsuranceClaimCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        active_policy = user.insurance_policies.filter(status='active').first()
        if not active_policy:
            return error_response(
                'No active insurance policy. Activate one first.',
                status=400
            )

        days_missed = serializer.validated_data['days_missed']
        reason = serializer.validated_data['reason']

        # Payout formula: (coverage_limit / 30) * days_missed
        daily_coverage = active_policy.coverage_limit / 30
        payout = (daily_coverage * days_missed).quantize(Decimal('0.01'))

        # Cap at coverage limit
        payout = min(payout, active_policy.coverage_limit)

        auto_approve = payout <= AUTO_APPROVE_THRESHOLD

        with db_transaction.atomic():
            claim = InsuranceClaim.objects.create(
                policy=active_policy,
                user=user,
                days_missed=days_missed,
                reason=reason,
                payout_amount=payout,
                funding_source='demo_float',
                status=(
                    InsuranceClaim.Status.AUTO_APPROVED
                    if auto_approve
                    else InsuranceClaim.Status.MANUAL_REVIEW
                ),
            )

            if auto_approve:
                # Disburse from demo float immediately
                try:
                    demo_float = DemoFloat.objects.select_for_update().get(id=1)
                    demo_float.disburse(payout)
                except (DemoFloat.DoesNotExist, ValueError) as e:
                    logger.error(f"Demo float insufficient for claim payout: {e}")
                    claim.status = InsuranceClaim.Status.MANUAL_REVIEW
                    claim.admin_notes = 'Auto-approve failed — demo float insufficient'
                    claim.save(update_fields=['status', 'admin_notes'])
                    return success_response({
                        'claim_id': str(claim.id),
                        'status': 'manual_review',
                        'payout_amount': str(payout),
                        'message': 'Claim submitted. Under review — payout within 24 hours.',
                    }, status=201)

                user.wallet.credit(payout)
                claim.paid_at = timezone.now()
                claim.save(update_fields=['status', 'paid_at'])

                from apps.payments.models import Transaction
                Transaction.objects.create(
                    user=user,
                    transaction_type=Transaction.Type.INSURANCE_PAYOUT,
                    amount=payout,
                    status=Transaction.Status.SUCCESS,
                    description=f'Insurance claim auto-approved — {days_missed} days missed',
                    metadata={
                        'claim_id': str(claim.id),
                        'source': 'demo_float',
                        'days_missed': days_missed,
                    },
                )

        from apps.scoring.tasks import recalculate_score
        recalculate_score.delay(str(user.id))

        if auto_approve:
            return success_response({
                'claim_id': str(claim.id),
                'status': 'auto_approved',
                'payout_amount': str(payout),
                'wallet_balance': str(user.wallet.balance),
                'message': f'Claim approved! ₦{payout} added to your wallet.',
            }, status=201)

        return success_response({
            'claim_id': str(claim.id),
            'status': 'manual_review',
            'payout_amount': str(payout),
            'message': (
                f'Claim of ₦{payout} submitted for review. '
                f'Payout within 24 hours if approved.'
            ),
        }, status=201)


class ClaimListView(APIView):
    """GET /api/financial/insurance/claims/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='claims_list',
        summary='List insurance claims',
        description='Get all insurance claims for current user',
        tags=['Financial Services'],
    )
    def get(self, request):
        claims = InsuranceClaim.objects.filter(user=request.user).order_by('-created_at')
        return success_response({
            'claims': InsuranceClaimSerializer(claims, many=True).data,
            'count': claims.count(),
        })