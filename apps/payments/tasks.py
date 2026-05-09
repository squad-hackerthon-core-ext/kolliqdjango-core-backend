from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def release_escrow_for_job(self, job_id: str, worker_id: str):
    from apps.payments.escrow import release_escrow
    try:
        release_escrow(job_id, worker_id)
    except Exception as exc:
        logger.error(f"release_escrow_for_job failed job={job_id} worker={worker_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def process_squad_webhook(payload: dict):
    """
    Routes Squad webhook events.
    Virtual account payments are the main event type we care about.
    """
    event_type = (payload.get('Event') or payload.get('event') or '').lower()
    data = payload.get('Body') or payload.get('data') or {}

    logger.info(f"Squad webhook received: {event_type}")

    if event_type in ('charge.success', 'virtual_account.payment', 'payment.success'):
        _handle_virtual_account_payment(data)
    elif event_type in ('transfer.success', 'payout.success'):
        _handle_transfer_success(data)
    else:
        logger.info(f"Unhandled Squad event: {event_type} — payload: {payload}")


def _handle_virtual_account_payment(data: dict):
    """
    A payment landed on one of our virtual accounts.
    Could be:
      A) Employer paying into KOLLIQ_ESCROW_VIRTUAL_ACCOUNT → match to job
      B) Customer paying Amina's personal virtual account → credit her wallet
    """
    from decimal import Decimal
    from django.conf import settings
    from apps.payments.escrow import match_escrow_payment_to_job
    from apps.wallets.models import Wallet
    from apps.payments.models import Transaction

    virtual_account = (
        data.get('virtual_account_number') or
        data.get('account_number') or ''
    )
    amount_kobo = int(data.get('amount', 0) or data.get('transaction_amount', 0))
    amount_naira = Decimal(str(amount_kobo)) / 100
    narration = data.get('transaction_remarks') or data.get('narration') or ''
    squad_ref = data.get('transaction_ref') or data.get('reference') or ''

    # ── Case A: Payment to escrow system account ──────────────────────────
    escrow_va = settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT
    if virtual_account == escrow_va or not virtual_account:
        # Try to match by narration reference
        matched = match_escrow_payment_to_job(narration, amount_naira, squad_ref)
        if not matched:
            logger.warning(
                f"Unmatched escrow payment: ₦{amount_naira} "
                f"narration='{narration}' ref={squad_ref}"
            )
        return

    # ── Case B: Payment to a user's personal virtual account (Amina) ─────
    try:
        wallet = Wallet.objects.select_related('user').get(
            squad_account_number=virtual_account
        )
    except Wallet.DoesNotExist:
        logger.warning(f"Payment to unknown virtual account: {virtual_account}")
        return

    wallet.credit(amount_naira)

    Transaction.objects.create(
        user=wallet.user,
        transaction_type=Transaction.Type.CREDIT,
        amount=amount_naira,
        status=Transaction.Status.SUCCESS,
        squad_reference=squad_ref,
        description=f"Payment received — {narration or 'via virtual account'}",
        metadata=data,
    )

    # Score recalculation — builds Amina's transaction history
    from apps.scoring.tasks import recalculate_score
    recalculate_score.delay(str(wallet.user_id))

    # SMS confirmation to trader
    from services.notifications import notify_trader_payment_received
    sender = data.get('sender_name') or data.get('customer_name') or 'a customer'
    notify_trader_payment_received.delay(
        str(wallet.user_id),
        str(amount_naira),
        str(wallet.balance),
        sender,
    )


def _handle_transfer_success(data: dict):
    """Outgoing transfer confirmed — update loan disbursement status."""
    reference = data.get('transaction_reference', '')
    logger.info(f"Transfer confirmed: {reference}")
    if 'loan-disburse' in reference:
        from apps.financial_services.models import Loan
        try:
            loan = Loan.objects.get(squad_disbursement_ref=reference)
            if loan.status == 'pending':
                loan.status = Loan.Status.ACTIVE
                loan.save(update_fields=['status', 'updated_at'])
        except Loan.DoesNotExist:
            pass