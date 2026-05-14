"""
Notification helpers — thin wrappers around ATService for specific platform events.
All notification functions are designed to be called from Celery tasks.
"""
from celery import shared_task
from services.africas_talking import ATService
import logging

logger = logging.getLogger(__name__)


def notify_employer_acceptance(application):
    """Tell employer a worker has accepted their job."""
    job = application.job
    worker = application.worker
    employer = job.employer

    message = (
        f"Kolliq: {worker.display_name} has accepted your job '{job.title}'. "
        f"Contact: {worker.phone}. "
        f"Reply 'done {str(job.id)[:8]}' when complete."
    )
    at = ATService()
    at.send_sms(employer.phone, message)
    logger.info(f"Notified employer {employer.phone} of acceptance by {worker.phone}")


@shared_task
def notify_worker_payment(user_id: str, amount: str, new_balance: str):
    """Tell worker their payment landed."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        message = (
            f"Kolliq: ₦{amount} has been added to your wallet. "
            f"New balance: ₦{new_balance}. "
            f"Keep completing jobs to grow your score!"
        )
        at = ATService()
        at.send_sms(user.phone, message)
    except User.DoesNotExist:
        logger.error(f"notify_worker_payment: User {user_id} not found")


@shared_task
def notify_trader_payment_received(user_id: str, amount: str, new_balance: str, sender: str):
    """Tell trader (Amina) they received payment."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        message = (
            f"Kolliq: You received ₦{amount} from {sender}. "
            f"Balance: ₦{new_balance}."
        )
        at = ATService()
        at.send_sms(user.phone, message)
    except User.DoesNotExist:
        logger.error(f"notify_trader_payment_received: User {user_id} not found")


@shared_task
def notify_loan_disbursed(user_id: str, amount: str, repayment_date: str):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        message = (
            f"Kolliq: ₦{amount} loan has been added to your wallet. "
            f"First repayment due: {repayment_date}. "
            f"Repay on time to grow your score and increase your limit."
        )
        at = ATService()
        at.send_sms(user.phone, message)
    except User.DoesNotExist:
        logger.error(f"notify_loan_disbursed: User {user_id} not found")

