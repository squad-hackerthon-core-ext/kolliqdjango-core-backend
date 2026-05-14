"""
Kolliq Escrow Engine — Virtual Account Implementation
=====================================================
Squad has no native escrow API. We simulate escrow using a
dedicated Kolliq system virtual account.

Flow:
  1. Employer posts job → we show them the escrow virtual account number
     + a payment reference (job ID short code) to include in narration
  2. Employer pays → Squad fires webhook with virtual account payment event
  3. Webhook handler matches payment to job via reference in narration
  4. Job marked escrow_funded = True → matching goes live
  5. Employer confirms done → Django calls Squad Transfers API
     to move 95% → worker's virtual account, 5% stays in platform account

Key principle: money never leaves Squad's rails.
We just move it between virtual accounts we control.
"""

from decimal import Decimal
from django.conf import settings
from django.db import transaction as db_transaction
import logging

logger = logging.getLogger(__name__)

PLATFORM_FEE_PERCENT = Decimal(str(settings.PLATFORM_FEE_PERCENT))


# ── Step 1: Give employer payment instructions ─────────────────────────────

def get_escrow_payment_instructions(job) -> dict:
    """
    Returns payment instructions shown to employer after posting a job.
    No API call needed — just return our escrow virtual account details.
    """
    short_ref = str(job.id).replace('-', '')[:12].upper()
    total_amount = float(job.pay_per_worker) * job.workers_needed

    # Store reference so webhook can match this job
    job.escrow_reference = short_ref
    job.save(update_fields=['escrow_reference', 'updated_at'])

    return {
        'account_number': settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT,
        'bank_name': 'Squad MFB',
        'account_name': 'Kolliq Escrow',
        'amount': total_amount,
        'reference': short_ref,
        'instruction': (
            f"Transfer exactly ₦{total_amount:,.0f} to the account above. "
            f"Include reference '{short_ref}' in your payment narration. "
            f"Job will go live within 60 seconds of payment confirmation."
        ),
    }


# ── Step 2: Webhook matches payment to job ─────────────────────────────────

def match_escrow_payment_to_job(narration: str, amount: Decimal, squad_reference: str) -> bool:
    """
    Called by webhook handler when a payment arrives on the escrow virtual account.
    Tries to match the narration to a pending job's escrow_reference.
    Returns True if matched and funded, False if no match found.
    """
    from apps.jobs.models import Job
    from apps.payments.models import Transaction

    # Search narration for any known escrow reference
    narration_upper = (narration or '').upper()
    pending_jobs = Job.objects.filter(
        escrow_funded=False,
        escrow_reference__isnull=False,
    ).exclude(escrow_reference='')

    matched_job = None
    for job in pending_jobs:
        if job.escrow_reference in narration_upper:
            matched_job = job
            break

    if not matched_job:
        logger.warning(
            f"Escrow payment received but no job matched. "
            f"Narration: '{narration}' Amount: ₦{amount}"
        )
        return False

    with db_transaction.atomic():
        matched_job.escrow_funded = True
        matched_job.save(update_fields=['escrow_funded', 'updated_at'])

        # Record the escrow hold transaction on employer's account
        Transaction.objects.create(
            user=matched_job.employer,
            transaction_type=Transaction.Type.ESCROW_HOLD,
            amount=amount,
            status=Transaction.Status.SUCCESS,
            squad_reference=squad_reference,
            job=matched_job,
            description=f"Escrow funded via virtual account for: {matched_job.title}",
            metadata={
                'job_id': str(matched_job.id),
                'escrow_reference': matched_job.escrow_reference,
                'narration': narration,
            }
        )

    logger.info(
        f"Escrow matched and funded: job={matched_job.id} "
        f"ref={matched_job.escrow_reference} amount=₦{amount}"
    )

    # Trigger worker matching notifications now job is live
    from apps.jobs.tasks import trigger_job_matching_notifications
    trigger_job_matching_notifications.delay(str(matched_job.id))

    return True


# ── Step 3: Release escrow to worker ──────────────────────────────────────

def release_escrow(job_id: str, worker_id: str):
    """
    Releases escrow to a worker after job completion.

    In simulated mode (pilot): credits worker wallet directly in DB,
    logs a transfer intent. No real Squad payout API call yet because
    we need Squad's transfer API approval for live payouts.

    In live mode: calls Squad Transfers API to move money from
    escrow virtual account → worker's virtual account.

    Switch via FINANCIAL_PARTNER_MODE setting.
    """
    from apps.jobs.models import Job
    from apps.payments.models import Transaction
    from django.contrib.auth import get_user_model

    User = get_user_model()
    partner_mode = settings.FINANCIAL_PARTNER_MODE

    with db_transaction.atomic():
        job = Job.objects.select_related('employer').get(id=job_id)
        worker = User.objects.select_related('wallet').get(id=worker_id)

        gross = job.pay_per_worker
        fee = (gross * PLATFORM_FEE_PERCENT / Decimal('100')).quantize(Decimal('0.01'))
        net_to_worker = gross - fee

        if partner_mode == 'live':
            _release_escrow_live(job, worker, gross, net_to_worker, fee)
        else:
            _release_escrow_simulated(job, worker, gross, net_to_worker, fee)

    logger.info(
        f"Escrow released [{partner_mode}]: "
        f"job={job_id} worker={worker_id} net=₦{net_to_worker} fee=₦{fee}"
    )

    # Recalculate worker's score + notify
    from apps.scoring.tasks import recalculate_score
    from services.notifications import notify_worker_payment

    worker.refresh_from_db()
    recalculate_score.delay(str(worker_id))
    notify_worker_payment.delay(
        str(worker_id),
        str(net_to_worker),
        str(worker.wallet.balance)
    )


def _release_escrow_simulated(job, worker, gross, net_to_worker, fee):
    """
    Pilot escrow release: update balances in DB directly.
    Records everything so switching to live mode is a one-line change.
    """
    from apps.payments.models import Transaction
    from apps.wallets.models import Wallet
    from django.conf import settings
 
    employer_wallet = job.employer.wallet
 
    # Error message MUST start with 'Insufficient escrow' to match test
    if employer_wallet.escrow_balance < gross:
        raise ValueError(
            f'Insufficient escrow balance. '
            f'Have ₦{employer_wallet.escrow_balance}, need ₦{gross}'
        )
 
    # Debit escrow from employer
    employer_wallet.escrow_balance -= gross
    employer_wallet.save(update_fields=['escrow_balance', 'updated_at'])
 
    # Credit worker wallet
    worker_wallet = worker.wallet
    worker_wallet.credit(net_to_worker)
 
    # Credit platform wallet
    try:
        platform_wallet = Wallet.objects.get(id=settings.ARISE_WALLET_ID)
        platform_wallet.credit(fee)
    except Wallet.DoesNotExist:
        pass
 
    # Three transaction records
    Transaction.objects.create(
        user=job.employer,
        transaction_type=Transaction.Type.ESCROW_RELEASE,
        amount=gross,
        status=Transaction.Status.SUCCESS,
        job=job,
        related_user=worker,
        description=f'Escrow released for: {job.title}',
        metadata={'mode': 'simulated'},
    )
    Transaction.objects.create(
        user=worker,
        transaction_type=Transaction.Type.CREDIT,
        amount=net_to_worker,
        status=Transaction.Status.SUCCESS,
        job=job,
        related_user=job.employer,
        description=f'Payment for: {job.title}',
        metadata={'mode': 'simulated'},
    )
    Transaction.objects.create(
        user=job.employer,
        transaction_type=Transaction.Type.PLATFORM_FEE,
        amount=fee,
        status=Transaction.Status.SUCCESS,
        job=job,
        description=f'Platform fee (5%) for: {job.title}',
        metadata={'mode': 'simulated'},
    )


def _release_escrow_live(job, worker, gross, net_to_worker, fee):
    """
    Live escrow release: Squad Transfers API pays worker's real bank account.
 
    Prerequisites:
      - Worker must have bank_account_number + bank_code saved on their wallet
        (via POST /api/wallets/bank-account/save/)
      - FINANCIAL_PARTNER_MODE = 'live' in settings
      - Squad secret key configured and transfer limits set
 
    Flow:
      merchant account (Squad) → worker's real bank account
      fee stays in merchant account (tracked via Transaction record)
    """
    from services.squad import SquadService
    from apps.payments.models import Transaction
 
    squad     = SquadService()
    reference = f"kolliq-payout-{job.id}-{worker.id}"[:100]
 
    worker_wallet = worker.wallet
 
    # ── Preflight: bank account must be saved and verified ────────────────────
    if not worker_wallet.bank_account_number:
        raise ValueError(
            f"Worker {worker.id} ({worker.full_name}) has not saved a bank account. "
            f"They must add their bank details before receiving payment."
        )
 
    if not worker_wallet.bank_account_verified:
        raise ValueError(
            f"Worker {worker.id} ({worker.full_name}) bank account is not verified. "
            f"Ask them to re-save their bank details via the app."
        )
 
    if not worker_wallet.bank_code:
        raise ValueError(
            f"Worker {worker.id} ({worker.full_name}) bank code is missing."
        )
 
    # ── Initiate transfer: merchant account → worker's bank ───────────────────
    logger.info(
        f"Initiating live payout: job={job.id} worker={worker.id} "
        f"amount=₦{net_to_worker} → {worker_wallet.bank_name} "
        f"***{worker_wallet.bank_account_number[-4:]}"
    )
 
    try:
        transfer_result = squad.initiate_transfer(
            amount_kobo=int(net_to_worker * 100),       # Squad expects kobo
            account_number=worker_wallet.bank_account_number,  # real bank acct
            bank_code=worker_wallet.bank_code,           # real bank code (e.g. '058')
            account_name=worker_wallet.bank_account_name or worker.full_name,
            reference=reference,
            narration=f"Kolliq payment: {job.title[:50]}",
        )
    except Exception as e:
        logger.error(
            f"Squad transfer failed: job={job.id} worker={worker.id} error={e}"
        )
        # Record failed transaction so we can retry/investigate
        Transaction.objects.create(
            user=worker,
            transaction_type=Transaction.Type.CREDIT,
            amount=net_to_worker,
            status=Transaction.Status.FAILED,
            job=job,
            squad_reference=reference,
            related_user=job.employer,
            description=f"Payment FAILED for: {job.title}",
            metadata={
                'mode':          'live',
                'error':         str(e),
                'bank_code':     worker_wallet.bank_code,
                'bank_name':     worker_wallet.bank_name,
                'account_last4': worker_wallet.bank_account_number[-4:],
            },
        )
        raise
 
    # ── Determine transaction status from Squad response ──────────────────────
    squad_status = transfer_result.get('status', '')
    tx_status = (
        Transaction.Status.SUCCESS
        if squad_status in ('success', 'successful')
        else Transaction.Status.PENDING   # Squad may process async
    )
 
    logger.info(
        f"Squad transfer response: status={squad_status} reference={reference}"
    )
 
    # ── Worker credit record ──────────────────────────────────────────────────
    Transaction.objects.create(
        user=worker,
        transaction_type=Transaction.Type.CREDIT,
        amount=net_to_worker,
        status=tx_status,
        job=job,
        squad_reference=reference,
        related_user=job.employer,
        description=f"Payment for: {job.title}",
        metadata={
            'mode':          'live',
            'bank_name':     worker_wallet.bank_name,
            'bank_code':     worker_wallet.bank_code,
            'account_name':  worker_wallet.bank_account_name,
            'account_last4': worker_wallet.bank_account_number[-4:],
            'squad_response': transfer_result,
        },
    )
 
    # ── Employer escrow release record ────────────────────────────────────────
    Transaction.objects.create(
        user=job.employer,
        transaction_type=Transaction.Type.ESCROW_RELEASE,
        amount=gross,
        status=tx_status,
        job=job,
        squad_reference=reference,
        related_user=worker,
        description=f"Escrow released for: {job.title}",
        metadata={
            'mode':            'live',
            'net_to_worker':   str(net_to_worker),
            'platform_fee':    str(fee),
        },
    )
 
    # ── Platform fee record (stays in merchant account) ───────────────────────
    Transaction.objects.create(
        user=job.employer,
        transaction_type=Transaction.Type.PLATFORM_FEE,
        amount=fee,
        status=Transaction.Status.SUCCESS,
        job=job,
        description=f"Platform fee (5%) for: {job.title}",
        metadata={
            'mode': 'live',
            'note': 'Fee retained in Squad merchant account',
        },
    )

    """
    Live escrow release: Squad Transfers API moves money between virtual accounts.
    Activated when FINANCIAL_PARTNER_MODE = 'live'.
    """
    from services.squad import SquadService
    from apps.payments.models import Transaction
    import uuid

    squad = SquadService()
    reference = f"kolliq-payout-{job.id}-{worker.id}"[:100]

    # Transfer from escrow VA → worker VA via Squad
    worker_wallet = worker.wallet
    if not worker_wallet.squad_account_number:
        raise ValueError(f"Worker {worker.id} has no Squad virtual account number")

    transfer_result = squad.initiate_transfer(
        amount_kobo=int(net_to_worker * 100),
        account_number=worker_wallet.squad_account_number,
        bank_code='000013',          # Squad MFB bank code
        account_name=worker.display_name,
        reference=reference,
        narration=f"Kolliq payment: {job.title}"
    )

    tx_status = (
        Transaction.Status.SUCCESS
        if transfer_result.get('status') == 'success'
        else Transaction.Status.PENDING
    )

    Transaction.objects.create(
        user=worker,
        transaction_type=Transaction.Type.CREDIT,
        amount=net_to_worker,
        status=tx_status,
        job=job,
        squad_reference=reference,
        related_user=job.employer,
        description=f"Payment for: {job.title}",
        metadata={'mode': 'live', 'squad_response': transfer_result},
    )

    Transaction.objects.create(
        user=job.employer,
        transaction_type=Transaction.Type.ESCROW_RELEASE,
        amount=gross,
        status=tx_status,
        job=job,
        squad_reference=reference,
        related_user=worker,
        description=f"Escrow released for: {job.title}",
        metadata={'mode': 'live'},
    )

    Transaction.objects.create(
        user=job.employer,
        transaction_type=Transaction.Type.PLATFORM_FEE,
        amount=fee,
        status=Transaction.Status.SUCCESS,
        job=job,
        description=f"Platform fee (5%) for: {job.title}",
    )