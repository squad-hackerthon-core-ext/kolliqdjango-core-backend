"""
Economic Identity Score — deterministic rules engine.
No ML in the pilot. Drop-in replaceable post-pilot.
"""
from decimal import Decimal


# ── Score thresholds for service unlocks ──────────────────────────────────────
SAVINGS_UNLOCK_SCORE = 20
INSURANCE_UNLOCK_SCORE = 40
LOAN_UNLOCK_SCORE = 60

# ── Point weights ─────────────────────────────────────────────────────────────
BASE_SCORE = 10
POINTS_PER_GIG = 5
POINTS_PER_TRANSACTION = 2
POINTS_PER_LOAN_REPAYMENT = 8
POINTS_PER_RATING = 3
POINTS_PER_INSURANCE_DAY = 1
SCORE_CAP = 100


def calculate_score(user) -> dict:
    """
    Recalculate a user's Economic Identity Score from scratch.
    Returns dict with 'score' and 'breakdown'.
    """
    from apps.jobs.models import JobApplication
    from apps.payments.models import Transaction

    breakdown = {
        'base': BASE_SCORE,
        'gigs_completed': 0,
        'transactions_recorded': 0,
        'loans_repaid': 0,
        'ratings_received': 0,
        'insurance_days': 0,
    }

    # Gigs completed
    gigs = JobApplication.objects.filter(
        worker=user,
        status='completed'
    ).count()
    breakdown['gigs_completed'] = gigs * POINTS_PER_GIG

    # Transactions recorded (trader payments, wallet credits)
    tx_count = Transaction.objects.filter(
        user=user,
        status='success',
        transaction_type='credit'
    ).count()
    breakdown['transactions_recorded'] = tx_count * POINTS_PER_TRANSACTION

    # Loan repayments
    loan_repayments = Transaction.objects.filter(
        user=user,
        status='success',
        transaction_type='loan_repayment'
    ).count()
    breakdown['loans_repaid'] = loan_repayments * POINTS_PER_LOAN_REPAYMENT

    # Ratings received
    from apps.jobs.models import Rating
    ratings = Rating.objects.filter(to_user=user).count()
    breakdown['ratings_received'] = ratings * POINTS_PER_RATING

    # Insurance premium days paid
    insurance_payments = Transaction.objects.filter(
        user=user,
        status='success',
        transaction_type='insurance_premium'
    ).count()
    breakdown['insurance_days'] = insurance_payments * POINTS_PER_INSURANCE_DAY

    raw_score = sum(breakdown.values())
    final_score = min(raw_score, SCORE_CAP)

    return {
        'score': final_score,
        'breakdown': breakdown,
    }


def get_unlocked_services(score: int) -> list:
    """Return list of service names unlocked at a given score."""
    unlocked = []
    if score >= SAVINGS_UNLOCK_SCORE:
        unlocked.append('micro_savings')
    if score >= INSURANCE_UNLOCK_SCORE:
        unlocked.append('micro_insurance')
    if score >= LOAN_UNLOCK_SCORE:
        unlocked.append('micro_loan')
    return unlocked


def get_score_summary(score: int) -> dict:
    """Human-readable summary for the user's dashboard."""
    return {
        'score': score,
        'max': SCORE_CAP,
        'tier': _get_tier(score),
        'next_unlock': _get_next_unlock(score),
        'unlocked_services': get_unlocked_services(score),
    }


def _get_tier(score: int) -> str:
    if score < 20:
        return 'starter'
    elif score < 40:
        return 'active'
    elif score < 60:
        return 'trusted'
    elif score < 80:
        return 'established'
    return 'champion'


def _get_next_unlock(score: int) -> dict | None:
    if score < SAVINGS_UNLOCK_SCORE:
        return {'service': 'micro_savings', 'points_needed': SAVINGS_UNLOCK_SCORE - score}
    if score < INSURANCE_UNLOCK_SCORE:
        return {'service': 'micro_insurance', 'points_needed': INSURANCE_UNLOCK_SCORE - score}
    if score < LOAN_UNLOCK_SCORE:
        return {'service': 'micro_loan', 'points_needed': LOAN_UNLOCK_SCORE - score}
    return None