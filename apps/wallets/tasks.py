from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def create_wallet_for_user(self, user_id: str):
    """
    Creates Wallet record + provisions Squad virtual account.
    Triggered by post_save signal on User creation.
    """
    from django.contrib.auth import get_user_model
    from services.squad import SquadService, SquadAPIError
    from apps.wallets.models import Wallet

    User = get_user_model()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"create_wallet_for_user: User {user_id} not found")
        return

    wallet, created = Wallet.objects.get_or_create(user=user)

    if not created and wallet.squad_creation_status == 'created':
        logger.info(f"Wallet already exists for {user_id}")
        return

    squad = SquadService()

    name_parts = (user.full_name or 'Kolliq User').strip().split(' ', 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else first_name

    try:
        result = squad.create_virtual_account(
            customer_identifier=str(user.id),
            first_name=first_name,
            last_name=last_name,
            phone=user.phone,
            email=f"{str(user.id)[:8]}@kolliq.app",
            # BVN left empty for pilot — required for production
            bvn='',
            dob='',
            gender='1',
            address=user.location_area or '',
        )

        wallet.squad_account_number = result['virtual_account_number']
        wallet.squad_account_name = f"{first_name} {last_name}"
        wallet.squad_bank_name = result.get('bank_name', 'GTBank')
        wallet.squad_customer_id = result.get('customer_identifier', str(user.id))
        wallet.squad_virtual_account_ref = result['virtual_account_number']
        wallet.squad_creation_status = 'created'
        wallet.save()

        logger.info(
            f"Squad VA created for {user.phone}: "
            f"{wallet.squad_account_number}"
        )

    except SquadAPIError as exc:
        wallet.squad_creation_status = 'failed'
        wallet.save(update_fields=['squad_creation_status'])
        logger.error(f"Squad VA creation failed for {user_id}: {exc} | raw={exc.raw}")
        raise self.retry(exc=exc)