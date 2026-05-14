import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def on_user_created(sender, instance, created, **kwargs):
    if created:
        from apps.wallets.tasks import create_wallet_for_user
        from apps.scoring.tasks import initialise_score_for_user

        create_wallet_for_user.delay(str(instance.id))
        initialise_score_for_user.delay(str(instance.id))


@receiver(post_save, sender=User)
def queue_squad_va_retry_on_failure(sender, instance, created, **kwargs):
    """
    Watches every User save. If squad_account_status just became 'failed',
    queues the retry_squad_virtual_account Celery task.

    Why post_save and not a direct .delay() call in the view?
    - The signal fires AFTER the DB row is committed, so the task worker
      will always find the user when it queries by ID.
    - Keeps the view lean — failure handling is not the view's concern.
    - Works for any code path that sets status='failed', not just the view.

    Note: No infinite loop risk — the task sets status to 'active' on success,
    and we only queue when status == 'failed', so it won't re-trigger itself.
    """
    from .tasks import retry_squad_virtual_account

    if instance.squad_account_status == 'failed':
        logger.info(
            f"[Signal] squad_account_status='failed' detected for user {instance.id}. "
            f"Queuing retry task."
        )
        retry_squad_virtual_account.delay(str(instance.id))