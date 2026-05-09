from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User


@receiver(post_save, sender=User)
def on_user_created(sender, instance, created, **kwargs):
    if created:
        # Import here to avoid circular imports
        from apps.wallets.tasks import create_wallet_for_user
        from apps.scoring.tasks import initialise_score_for_user
        create_wallet_for_user.delay(str(instance.id))
        initialise_score_for_user.delay(str(instance.id))