from celery import shared_task
from decimal import Decimal
from django.conf import settings
from django.db.models import Sum
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
    from decimal import Decimal
    from django.conf import settings
    from apps.payments.escrow import match_escrow_payment_to_job
    from apps.wallets.models import Wallet
    from apps.payments.models import Transaction
    
    logger.info("=" * 60)
    logger.info("Squad webhook received - Processing payment")
    logger.info("=" * 60)
    
    # Squad sends payment data directly at the top level
    # Check if this looks like a payment (has transaction_reference and virtual_account_number)
    if payload.get('transaction_reference') and payload.get('virtual_account_number'):
        logger.info("Direct payment payload detected - processing")
        _handle_virtual_account_payment(payload)
        return
    
    # Fallback: Try wrapped event format
    event_type = (payload.get('Event') or payload.get('event') or '').lower()
    data = payload.get('Body') or payload.get('data') or {}
    
    if event_type in ('charge.success', 'virtual_account.payment', 'payment.success'):
        _handle_virtual_account_payment(data)
    elif event_type in ('transfer.success', 'payout.success'):
        _handle_transfer_success(data)
    else:
        logger.warning(f"Unhandled Squad event type: {event_type}")


def _handle_virtual_account_payment(data: dict):
    """
    A payment landed on one of our virtual accounts.
    """
    from decimal import Decimal
    from django.conf import settings
    from apps.payments.escrow import match_escrow_payment_to_job
    from apps.wallets.models import Wallet
    from apps.payments.models import Transaction

    logger.info("-" * 40)
    logger.info("Processing payment")
    logger.info("-" * 40)
    
    # Squad sends these fields directly in the payload
    virtual_account = data.get('virtual_account_number') or data.get('account_number', '')
    amount_str = data.get('principal_amount') or data.get('settled_amount') or data.get('amount', '0')
    narration = data.get('remarks') or data.get('transaction_remarks') or data.get('narration', '')
    squad_ref = data.get('transaction_reference') or data.get('transaction_ref') or data.get('reference', '')
    sender_name = data.get('sender_name') or data.get('customer_name') or 'a customer'
    
    logger.info(f"Virtual account: {virtual_account}")
    logger.info(f"Amount string: {amount_str}")
    logger.info(f"Reference: {squad_ref}")
    
    # Parse amount - remove commas if any
    try:
        amount_naira = Decimal(str(amount_str).replace(',', ''))
        logger.info(f"Parsed amount: ₦{amount_naira}")
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to parse amount: {amount_str} - {e}")
        return
    
    # Check if this is escrow account
    escrow_va = getattr(settings, 'KOLLIQ_ESCROW_VIRTUAL_ACCOUNT', None)
    logger.info(f"Escrow VA setting: {escrow_va}")
    
    if virtual_account == escrow_va:
        logger.info("Payment to ESCROW account")
        matched = match_escrow_payment_to_job(narration, amount_naira, squad_ref)
        if not matched:
            logger.warning(f"Unmatched escrow payment: ₦{amount_naira}")
        return
    
    # Find user's wallet
    logger.info(f"Looking for wallet with account: {virtual_account}")
    
    try:
        wallet = Wallet.objects.select_related('user').get(
            squad_account_number=virtual_account
        )
        logger.info(f"✅ Found wallet for user: {wallet.user.phone if wallet.user else 'Unknown'}")
        logger.info(f"💰 Current balance: ₦{wallet.balance}")
    except Wallet.DoesNotExist:
        logger.error(f"❌ Wallet not found for account: {virtual_account}")
        return
    
    # Credit the wallet
    wallet.credit(amount_naira)
    logger.info(f"💰 New balance: ₦{wallet.balance}")
    
    # Create transaction
    transaction = Transaction.objects.create(
        user=wallet.user,
        transaction_type=Transaction.Type.CREDIT,
        amount=amount_naira,
        status=Transaction.Status.SUCCESS,
        squad_reference=squad_ref,
        description=f"Payment received from {sender_name} — {narration[:100] if narration else 'via virtual account'}",
        metadata=data,
    )
    logger.info(f"✅ Transaction created: {transaction.id}")
    
    # Trigger score recalculation
    from apps.scoring.tasks import recalculate_score
    recalculate_score.delay(str(wallet.user_id))
    
    # Send SMS notification
    from services.notifications import notify_trader_payment_received
    notify_trader_payment_received.delay(
        str(wallet.user_id),
        str(amount_naira),
        str(wallet.balance),
        sender_name,
    )
    
    logger.info(f"✅ Payment of ₦{amount_naira} successfully processed")


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



DRIFT_ALERT_THRESHOLD = Decimal(
    str(getattr(settings, 'RECONCILIATION_DRIFT_THRESHOLD', '5000.00'))
)
 
# Alert if drift exceeds this % of expected balance
DRIFT_PERCENT_THRESHOLD = Decimal(
    str(getattr(settings, 'RECONCILIATION_DRIFT_PERCENT', '2.0'))
)
 
 
# ── Main Task ─────────────────────────────────────────────────────────────────
 
@shared_task(
    name='apps.payments.tasks.reconciliation.reconcile_merchant_account',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def reconcile_merchant_account(self):
    """
    Core reconciliation task.
    Runs every 6 hours via Celery Beat.
    """
    from apps.payments.models import Transaction, ReconciliationReport
 
    logger.info('🔍 Starting merchant account reconciliation...')
    started_at = timezone.now()
 
    # ── Step 1: Calculate expected balance from DB ────────────────────────────
    expected, breakdown = _calculate_expected_balance()
 
    # ── Step 2: Fetch actual balance from Squad API ───────────────────────────
    try:
        actual = _fetch_squad_merchant_balance()
    except Exception as e:
        logger.error(f'Reconciliation failed — could not fetch Squad balance: {e}')
        _save_report(
            status='error',
            expected=expected,
            actual=None,
            drift=None,
            breakdown=breakdown,
            error=str(e),
            started_at=started_at,
        )
        return {
            'status': 'error',
            'message': f'Squad API unavailable: {e}',
        }
 
    # ── Step 3: Calculate drift ───────────────────────────────────────────────
    drift         = actual - expected
    drift_abs     = abs(drift)
    drift_percent = (
        (drift_abs / expected * 100)
        if expected > 0
        else Decimal('0')
    )
 
    # ── Step 4: Determine alert level ────────────────────────────────────────
    is_critical = (
        drift_abs > DRIFT_ALERT_THRESHOLD or
        drift_percent > DRIFT_PERCENT_THRESHOLD
    )
 
    status = 'critical' if is_critical else 'ok'
 
    # ── Step 5: Log result ────────────────────────────────────────────────────
    log_fn = logger.critical if is_critical else logger.info
    log_fn(
        f'Reconciliation [{status.upper()}] | '
        f'Expected: ₦{expected:,.2f} | '
        f'Actual: ₦{actual:,.2f} | '
        f'Drift: ₦{drift:+,.2f} ({drift_percent:.2f}%)'
    )
 
    if is_critical:
        logger.critical(
            f'⚠️  MERCHANT BALANCE DRIFT EXCEEDS THRESHOLD!\n'
            f'   Expected : ₦{expected:,.2f}\n'
            f'   Actual   : ₦{actual:,.2f}\n'
            f'   Drift    : ₦{drift:+,.2f} ({drift_percent:.2f}%)\n'
            f'   Breakdown: {breakdown}'
        )
        _fire_alert(expected, actual, drift, drift_percent, breakdown)
 
    # ── Step 6: Save report ───────────────────────────────────────────────────
    report = _save_report(
        status=status,
        expected=expected,
        actual=actual,
        drift=drift,
        breakdown=breakdown,
        error=None,
        started_at=started_at,
    )
 
    logger.info(f'✅ Reconciliation complete. Report ID: {report.id}')
 
    return {
        'status':          status,
        'expected':        str(expected),
        'actual':          str(actual),
        'drift':           str(drift),
        'drift_percent':   str(drift_percent),
        'is_critical':     is_critical,
        'report_id':       str(report.id),
    }
 
 
# ── Expected Balance Calculator ───────────────────────────────────────────────
 
def _calculate_expected_balance() -> tuple[Decimal, dict]:
    """
    Calculates what the Squad merchant account SHOULD contain based on
    all successful Transaction records in our DB.
 
    Logic:
        + All ESCROW_HOLD amounts         (employers paid in)
        - All CREDIT amounts (SUCCESS)    (workers paid out)
        - All CREDIT amounts (PENDING)    (in-flight payouts — Squad already debited)
        + All PLATFORM_FEE amounts        (our cut, stays in merchant acct)
 
    Note: PENDING credits are subtracted because Squad debits the merchant
    account immediately when a transfer is initiated, even if the credit
    to the recipient is still processing.
    """
    from apps.payments.models import Transaction
 
    TxType   = Transaction.Type
    TxStatus = Transaction.Status
 
    def total(tx_type, statuses):
        result = Transaction.objects.filter(
            transaction_type=tx_type,
            status__in=statuses,
        ).aggregate(total=Sum('amount'))['total']
        return result or Decimal('0')
 
    escrow_in    = total(TxType.ESCROW_HOLD,    [TxStatus.SUCCESS])
    paid_out     = total(TxType.CREDIT,         [TxStatus.SUCCESS, TxStatus.PENDING])
    platform_fee = total(TxType.PLATFORM_FEE,   [TxStatus.SUCCESS])
 
    # Wallet top-ups / demo floats that came IN to merchant account
    # (if you have a DEPOSIT or TOP_UP transaction type, include it here)
    deposits = Decimal('0')
    if hasattr(TxType, 'DEPOSIT'):
        deposits = total(TxType.DEPOSIT, [TxStatus.SUCCESS])
 
    expected = escrow_in - paid_out + platform_fee + deposits
 
    breakdown = {
        'escrow_in':    str(escrow_in),
        'paid_out':     str(paid_out),
        'platform_fee': str(platform_fee),
        'deposits':     str(deposits),
        'expected':     str(expected),
    }
 
    logger.debug(f'Expected balance breakdown: {breakdown}')
    return expected, breakdown
 
 
# ── Squad Balance Fetcher ─────────────────────────────────────────────────────
 
def _fetch_squad_merchant_balance() -> Decimal:
    """
    Fetches the actual Squad merchant account balance via Squad's API.
 
    Squad endpoint:
        GET /merchant/balance
        Authorization: Bearer {SQUAD_SECRET_KEY}
 
    Response:
        { "status": 200, "data": { "balance": 500000 } }  ← in kobo
    """
    import requests
 
    url = f"{settings.SQUAD_BASE_URL}/merchant/balance"
    headers = {
        'Authorization': f'Bearer {settings.SQUAD_SECRET_KEY}',
        'Content-Type':  'application/json',
    }
 
    response = requests.get(url, headers=headers, timeout=15)
    data     = response.json()
 
    if response.status_code != 200 or data.get('status') not in (200, '200'):
        raise ValueError(
            f"Squad balance API error: {data.get('message', 'Unknown error')}"
        )
 
    balance_kobo = data.get('data', {}).get('balance', 0)
 
    # Squad returns balance in kobo — convert to naira
    balance_naira = Decimal(str(balance_kobo)) / Decimal('100')
 
    logger.debug(f'Squad merchant balance: ₦{balance_naira:,.2f}')
    return balance_naira
 
 
# ── Report Saver ──────────────────────────────────────────────────────────────
 
def _save_report(status, expected, actual, drift, breakdown, error, started_at):
    """Save reconciliation result to DB."""
    from apps.payments.models import ReconciliationReport
 
    return ReconciliationReport.objects.create(
        status=status,
        expected_balance=expected,
        actual_balance=actual,
        drift=drift,
        drift_percent=(
            abs(drift) / expected * 100
            if expected and expected > 0 and drift is not None
            else None
        ),
        breakdown=breakdown,
        error_message=error or '',
        ran_at=started_at,
        completed_at=timezone.now(),
    )
 
 
# ── Alert Dispatcher ──────────────────────────────────────────────────────────
 
def _fire_alert(expected, actual, drift, drift_percent, breakdown):
    """
    Fire alerts when drift is critical.
    Tries Slack first, falls back to email.
    Add/remove channels here as needed.
    """
    message = (
        f"🚨 *Kolliq Merchant Balance Drift Alert*\n"
        f"Expected : ₦{expected:,.2f}\n"
        f"Actual   : ₦{actual:,.2f}\n"
        f"Drift    : ₦{drift:+,.2f} ({drift_percent:.2f}%)\n"
        f"Breakdown: Escrow in ₦{breakdown['escrow_in']} | "
        f"Paid out ₦{breakdown['paid_out']} | "
        f"Fees ₦{breakdown['platform_fee']}\n"
        f"Action: Check Squad dashboard and transaction logs immediately."
    )
 
    # ── Slack ─────────────────────────────────────────────────────────────────
    slack_webhook = getattr(settings, 'SLACK_ALERT_WEBHOOK_URL', None)
    if slack_webhook:
        try:
            import requests
            requests.post(
                slack_webhook,
                json={'text': message},
                timeout=5,
            )
            logger.info('Reconciliation Slack alert sent.')
        except Exception as e:
            logger.warning(f'Slack alert failed: {e}')
 
    # ── Email ─────────────────────────────────────────────────────────────────
    alert_emails = getattr(settings, 'RECONCILIATION_ALERT_EMAILS', [])
    if alert_emails:
        try:
            from django.core.mail import send_mail
            send_mail(
                subject='🚨 Kolliq Merchant Balance Drift Alert',
                message=message.replace('*', '').replace('_', ''),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=alert_emails,
                fail_silently=True,
            )
            logger.info(f'Reconciliation email alert sent to {alert_emails}.')
        except Exception as e:
            logger.warning(f'Email alert failed: {e}')
