import logging
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone

logger = logging.getLogger(__name__)

# Maximum number of retry attempts before giving up
MAX_RETRIES = 5

# Exponential backoff delays in seconds:
# Attempt 1 → 1 min, 2 → 4 min, 3 → 9 min, 4 → 16 min, 5 → 25 min
def backoff(attempt: int) -> int:
    return 60 * (attempt ** 2)


@shared_task(
    bind=True,
    max_retries=MAX_RETRIES,
    name='users.tasks.retry_squad_virtual_account',
)
def retry_squad_virtual_account(self, user_id: str):
    """
    Retries Squad virtual account creation for a user whose initial
    attempt failed (e.g. due to timeout or API error during registration).

    Queued automatically via a Django post_save signal whenever
    squad_account_status is set to 'failed'.

    Retries up to MAX_RETRIES times with exponential backoff.
    On final failure, squad_account_status is set to 'permanently_failed'
    so ops/support can identify and manually resolve affected users.
    """
    # Import here to avoid circular imports at module load time
    from django.contrib.auth import get_user_model
    from apps.wallets.models import Wallet
    from services.squad import SquadService

    User = get_user_model()

    # ── Guard: fetch user ──────────────────────────────────────────────────
    try:
        user = User.objects.select_related('wallet').get(id=user_id)
    except User.DoesNotExist:
        # User was deleted between task enqueue and execution — nothing to do
        logger.warning(f"[Squad Retry] User {user_id} not found. Aborting task.")
        return

    # ── Guard: skip if VA already active ──────────────────────────────────
    # Handles the race condition where another retry already succeeded,
    # or the user somehow got a VA through another path.
    if user.squad_account_status == 'active':
        logger.info(f"[Squad Retry] User {user_id} already has an active VA. Skipping.")
        return

    # ── Attempt Squad VA creation ──────────────────────────────────────────
    logger.info(
        f"[Squad Retry] Attempting VA creation for user {user_id} "
        f"(attempt {self.request.retries + 1}/{MAX_RETRIES})"
    )

    try:
        full_name = user.full_name or ''
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ''
        middle_name = name_parts[2] if len(name_parts) >= 3 else ''
        last_name = name_parts[1] if len(name_parts) >= 1 else 'User'

        dob = ''
        if user.date_of_birth:
            dob = user.date_of_birth.strftime('%m/%d/%Y')

        gender = '1'
        if user.gender == 'F':
            gender = '2'

        squad_service = SquadService()
        squad_response = squad_service.create_virtual_account(
            customer_identifier=str(user.id),
            first_name=first_name or full_name[:50] or user.phone,
            last_name=last_name,
            middle_name=middle_name,
            phone=user.phone,
            email=user.email or f"{user.phone}@kolliq.ng",
            dob=dob,
            bvn=user.bvn or '',
            gender=gender,
            address=user.address or '',
        )

        # ── Success: persist VA details ────────────────────────────────────
        user.squad_account_number = squad_response.get('squad_account_number')
        user.squad_bank_name = squad_response.get('squad_bank_name', 'GTBank')
        user.squad_account_status = 'active'
        user.squad_account_created_at = timezone.now()
        user.save(update_fields=[
            'squad_account_number',
            'squad_bank_name',
            'squad_account_status',
            'squad_account_created_at',
        ])

        try:
            wallet = Wallet.objects.get(user=user)
            wallet.squad_account_number = squad_response.get('squad_account_number')
            wallet.squad_bank_name = squad_response.get('squad_bank_name', 'GTBank')
            wallet.save(update_fields=['squad_account_number', 'squad_bank_name'])
        except Wallet.DoesNotExist:
            logger.warning(f"[Squad Retry] Wallet not found for user {user_id} after VA success.")

        logger.info(
            f"[Squad Retry] VA created successfully for user {user_id}: "
            f"{user.squad_account_number}"
        )

    except Exception as exc:
        # ── Failure: decide whether to retry or give up ────────────────────
        attempt_number = self.request.retries + 1
        delay = backoff(attempt_number)

        logger.error(
            f"[Squad Retry] Attempt {attempt_number}/{MAX_RETRIES} failed for user {user_id}: "
            f"{str(exc)}. Retrying in {delay}s.",
            exc_info=True,
        )

        try:
            # countdown=delay tells Celery to wait `delay` seconds before next attempt
            raise self.retry(exc=exc, countdown=delay)

        except MaxRetriesExceededError:
            # All retries exhausted — mark permanently failed for manual intervention
            logger.critical(
                f"[Squad Retry] All {MAX_RETRIES} retries exhausted for user {user_id}. "
                f"Marking as permanently_failed. Manual intervention required."
            )
            user.squad_account_status = 'permanently_failed'
            user.save(update_fields=['squad_account_status'])