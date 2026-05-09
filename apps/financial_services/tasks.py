"""
Celery beat tasks for scheduled financial operations:
- Daily savings interest accrual
- Daily insurance premium deductions
- Weekly loan repayment processing
- Hourly fraud detection sweep
"""
from celery import shared_task
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

DAILY_INTEREST_RATE = Decimal(str(settings.SAVINGS_ANNUAL_INTEREST_RATE)) / 365 / 100


@shared_task
def accrue_daily_savings_interest():
    """
    Runs at midnight. Adds daily interest to every savings pot with a balance.
    Annual rate: 5% → daily rate: 5/365/100
    """
    from .models import SavingsPot
    from apps.payments.models import Transaction

    pots = SavingsPot.objects.filter(balance__gt=0).select_related('user')
    total_accrued = Decimal('0')
    count = 0

    for pot in pots:
        interest = (pot.balance * DAILY_INTEREST_RATE).quantize(Decimal('0.01'))
        if interest < Decimal('0.01'):
            continue

        pot.balance += interest
        pot.total_interest_earned += interest
        pot.save(update_fields=['balance', 'total_interest_earned', 'updated_at'])

        Transaction.objects.create(
            user=pot.user,
            transaction_type=Transaction.Type.SAVINGS_DEPOSIT,
            amount=interest,
            status=Transaction.Status.SUCCESS,
            description=f'Daily savings interest ({settings.SAVINGS_ANNUAL_INTEREST_RATE}% p.a.)',
            metadata={'type': 'interest_accrual'},
        )

        total_accrued += interest
        count += 1

    logger.info(f"Savings interest accrued: {count} pots, total ₦{total_accrued}")


@shared_task
def deduct_daily_insurance_premiums():
    """
    Runs at 6am daily. Deducts premium from every active insurance policy holder.
    If wallet is empty: pauses policy (doesn't cancel — realistic behavior).
    """
    from .models import InsurancePolicy
    from apps.payments.models import Transaction

    active_policies = InsurancePolicy.objects.filter(
        status='active'
    ).select_related('user', 'user__wallet')

    deducted = 0
    paused = 0

    for policy in active_policies:
        user = policy.user
        try:
            wallet = user.wallet
        except Exception:
            continue

        premium = policy.daily_premium

        if wallet.balance < premium:
            # Pause policy — wallet dry
            policy.status = InsurancePolicy.Status.PAUSED
            policy.save(update_fields=['status', 'updated_at'])
            paused += 1

            # Notify user
            from services.africas_talking import ATService
            at = ATService()
            at.send_sms(
                user.phone,
                f"Kolliq: Your insurance policy paused — insufficient balance. "
                f"Top up your wallet to reactivate. Dial *347*123# or open app."
            )
            continue

        wallet.debit(premium)

        policy.days_active += 1
        policy.total_premiums_paid += premium
        policy.save(update_fields=['days_active', 'total_premiums_paid', 'updated_at'])

        Transaction.objects.create(
            user=user,
            transaction_type=Transaction.Type.INSURANCE_PREMIUM,
            amount=premium,
            status=Transaction.Status.SUCCESS,
            description=f'Insurance premium — Day {policy.days_active}',
            metadata={'policy_id': str(policy.id), 'source': 'demo_float'},
        )

        deducted += 1

    # Recalculate scores for all affected users (insurance days = score points)
    from apps.scoring.tasks import recalculate_score
    for policy in active_policies:
        recalculate_score.delay(str(policy.user_id))

    logger.info(f"Insurance premiums: {deducted} deducted, {paused} paused")


@shared_task
def process_weekly_loan_repayments():
    """
    Runs every Monday at 8am.
    Auto-deducts the weekly loan installment from active loan holders' wallets.
    If wallet is empty → marks installment missed, moves toward defaulted.
    """
    from .models import Loan
    from apps.payments.models import Transaction
    from decimal import Decimal

    today = timezone.now().date().isoformat()
    active_loans = Loan.objects.filter(
        status__in=['active', 'partially_repaid']
    ).select_related('user', 'user__wallet')

    processed = 0
    missed = 0

    for loan in active_loans:
        # Find this week's installment
        due_installment = None
        for installment in loan.repayment_schedule:
            if not installment.get('paid') and installment['due_date'] <= today:
                due_installment = installment
                break

        if not due_installment:
            continue

        amount = Decimal(due_installment['amount'])
        user = loan.user

        try:
            wallet = user.wallet
        except Exception:
            continue

        if wallet.balance < amount:
            # Mark installment missed
            due_installment['missed'] = True
            due_installment['missed_at'] = timezone.now().isoformat()
            loan.save(update_fields=['repayment_schedule', 'updated_at'])
            missed += 1

            # Check if loan should be defaulted (2+ missed installments)
            missed_count = sum(1 for i in loan.repayment_schedule if i.get('missed'))
            if missed_count >= 2:
                loan.status = Loan.Status.DEFAULTED
                loan.save(update_fields=['status', 'updated_at'])
                # Flag user for review
                user.is_flagged = True
                user.flag_reason = f'Loan default — {missed_count} missed installments'
                user.save(update_fields=['is_flagged', 'flag_reason'])
                logger.warning(f"Loan defaulted for {user.phone}: {loan.id}")

            from services.africas_talking import ATService
            at = ATService()
            at.send_sms(
                user.phone,
                f"Kolliq: Loan repayment of ₦{amount} due today. "
                f"Insufficient balance. Top up your wallet immediately "
                f"to avoid score impact. Dial *347*123#."
            )
            continue

        # Deduct installment
        wallet.debit(amount)
        loan.amount_repaid += amount
        due_installment['paid'] = True
        due_installment['paid_at'] = timezone.now().isoformat()

        if loan.amount_repaid >= loan.total_repayable:
            loan.status = Loan.Status.REPAID
        else:
            loan.status = Loan.Status.PARTIALLY_REPAID

        loan.save(update_fields=['amount_repaid', 'status', 'repayment_schedule', 'updated_at'])

        # Return to demo float
        from .models import DemoFloat
        try:
            demo_float = DemoFloat.objects.get(id=1)
            demo_float.receive_repayment(amount)
        except DemoFloat.DoesNotExist:
            pass

        Transaction.objects.create(
            user=user,
            transaction_type=Transaction.Type.LOAN_REPAYMENT,
            amount=amount,
            status=Transaction.Status.SUCCESS,
            description=f'Auto weekly loan repayment',
            metadata={'loan_id': str(loan.id), 'source': 'demo_float'},
        )

        from apps.scoring.tasks import recalculate_score
        recalculate_score.delay(str(user.id))

        processed += 1

    logger.info(f"Weekly loan repayments: {processed} processed, {missed} missed")


@shared_task
def fraud_detection_sweep():
    """
    Runs hourly. Flags suspicious patterns.
    Rule 1: Job accepted + completed in < 30 minutes
    Rule 2: > 10 wallet credits in 1 hour
    Rule 3: Loan application within 24 hours of account creation
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    from apps.jobs.models import JobApplication
    from apps.payments.models import Transaction

    User = get_user_model()
    now = timezone.now()
    one_hour_ago = now - timedelta(hours=1)
    thirty_mins_ago = now - timedelta(minutes=30)

    flagged_count = 0

    # Rule 1: Job completed suspiciously fast
    suspicious_completions = JobApplication.objects.filter(
        status='completed',
        completed_at__gte=thirty_mins_ago,
        accepted_at__gte=thirty_mins_ago,
    ).select_related('worker')

    for app in suspicious_completions:
        if app.completed_at and app.accepted_at:
            delta = app.completed_at - app.accepted_at
            if delta.total_seconds() < 1800:  # < 30 minutes
                worker = app.worker
                if not worker.is_flagged:
                    worker.is_flagged = True
                    worker.flag_reason = (
                        f'Job {app.job_id} accepted and completed in '
                        f'{int(delta.total_seconds() / 60)} minutes'
                    )
                    worker.save(update_fields=['is_flagged', 'flag_reason'])
                    flagged_count += 1
                    logger.warning(
                        f"Fraud flag [Rule 1 — fast completion]: {worker.phone}"
                    )

    # Rule 2: > 10 credits in 1 hour
    from django.db.models import Count
    high_frequency = (
        Transaction.objects
        .filter(
            transaction_type='credit',
            status='success',
            created_at__gte=one_hour_ago,
        )
        .values('user_id')
        .annotate(count=Count('id'))
        .filter(count__gt=10)
    )

    for entry in high_frequency:
        try:
            user = User.objects.get(id=entry['user_id'])
            if not user.is_flagged:
                user.is_flagged = True
                user.flag_reason = f"{entry['count']} credits in 1 hour"
                user.save(update_fields=['is_flagged', 'flag_reason'])
                flagged_count += 1
                logger.warning(f"Fraud flag [Rule 2 — high frequency]: {user.phone}")
        except User.DoesNotExist:
            pass

    # Rule 3: Loan application < 24h after account creation
    new_borrowers = Loan.objects.filter(
        created_at__gte=now - timedelta(hours=24),
    ).select_related('user')

    for loan in new_borrowers:
        user = loan.user
        account_age = (now - user.created_at).total_seconds() / 3600
        if account_age < 24 and not user.is_flagged:
            user.is_flagged = True
            user.flag_reason = f'Loan applied {account_age:.1f}h after account creation'
            user.save(update_fields=['is_flagged', 'flag_reason'])
            flagged_count += 1
            logger.warning(f"Fraud flag [Rule 3 — early loan]: {user.phone}")

    if flagged_count:
        logger.info(f"Fraud sweep: {flagged_count} users flagged this hour")