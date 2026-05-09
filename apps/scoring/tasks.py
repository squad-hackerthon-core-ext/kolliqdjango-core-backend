from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def initialise_score_for_user(user_id: str):
    """Creates the initial EconomicIdentityScore record at 10 pts."""
    from django.contrib.auth import get_user_model
    from apps.scoring.models import EconomicIdentityScore

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        EconomicIdentityScore.objects.get_or_create(
            user=user,
            defaults={'score': 10, 'breakdown': {'base': 10}}
        )
        logger.info(f"Score initialised for user {user_id}")
    except User.DoesNotExist:
        logger.error(f"initialise_score_for_user: User {user_id} not found")


@shared_task
def recalculate_score(user_id: str):
    """
    Full recalculation of a user's Economic Identity Score.
    Call this after any scoring event: gig complete, payment received, loan repaid, rating given.
    """
    from django.contrib.auth import get_user_model
    from apps.scoring.models import EconomicIdentityScore
    from apps.scoring.engine import calculate_score, get_unlocked_services

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"recalculate_score: User {user_id} not found")
        return

    result = calculate_score(user)
    score_obj, _ = EconomicIdentityScore.objects.get_or_create(user=user)

    old_score = score_obj.score
    score_obj.score = result['score']
    score_obj.breakdown = result['breakdown']

    # Update unlock flags
    unlocked = get_unlocked_services(result['score'])
    score_obj.savings_unlocked = 'micro_savings' in unlocked
    score_obj.insurance_unlocked = 'micro_insurance' in unlocked
    score_obj.loan_unlocked = 'micro_loan' in unlocked
    score_obj.save()

    logger.info(f"Score recalculated for {user.phone}: {old_score} → {result['score']}")

    # Fire notification if new services unlocked
    if result['score'] > old_score:
        _notify_score_increase.delay(user_id, old_score, result['score'])


@shared_task
def _notify_score_increase(user_id: str, old_score: int, new_score: int):
    """Send SMS notification when score grows and unlocks something."""
    from django.contrib.auth import get_user_model
    from apps.scoring.engine import get_unlocked_services
    from services.africas_talking import ATService

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    old_unlocked = set(get_unlocked_services(old_score))
    new_unlocked = set(get_unlocked_services(new_score))
    newly_unlocked = new_unlocked - old_unlocked

    if newly_unlocked:
        service_names = {
            'micro_savings': 'Micro-Savings',
            'micro_insurance': 'Micro-Insurance',
            'micro_loan': 'Micro-Loan',
        }
        services_text = ' and '.join(service_names.get(s, s) for s in newly_unlocked)
        message = (
            f"Kolliq: Your score grew to {new_score}! "
            f"You've unlocked {services_text}. "
            f"Open the app or dial *347*123# to activate."
        )
        at = ATService()
        at.send_sms(user.phone, message)