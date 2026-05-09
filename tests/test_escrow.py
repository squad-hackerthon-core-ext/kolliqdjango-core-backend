import pytest
from decimal import Decimal
from unittest.mock import patch
from apps.payments.escrow import (
    get_escrow_payment_instructions,
    match_escrow_payment_to_job,
    release_escrow,
)


@pytest.mark.django_db
class TestEscrowInstructions:

    def test_returns_va_account_number(self, open_job, settings):
        settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT = '0123456789'
        result = get_escrow_payment_instructions(open_job)
        assert result['account_number'] == '0123456789'
        assert result['account_name'] == 'Kolliq Escrow'

    def test_reference_stored_on_job(self, open_job, settings):
        settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT = '0123456789'
        result = get_escrow_payment_instructions(open_job)
        open_job.refresh_from_db()
        assert open_job.escrow_reference == result['reference']
        assert len(result['reference']) > 0

    def test_amount_includes_all_workers(self, make_job, settings):
        settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT = '0123456789'
        job = make_job(pay=Decimal('3500'), workers_needed=3)
        result = get_escrow_payment_instructions(job)
        assert result['amount'] == 10500.0


@pytest.mark.django_db
class TestEscrowMatching:

    def test_payment_matches_job_by_narration(self, open_job, employer_wallet, settings):
        settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT = '0123456789'
        # Give job a reference
        open_job.escrow_reference = 'TESTREF001'
        open_job.escrow_funded = False
        open_job.save()

        matched = match_escrow_payment_to_job(
            narration='Payment for TESTREF001 delivery',
            amount=Decimal('3500'),
            squad_reference='SQ123456',
        )
        assert matched is True
        open_job.refresh_from_db()
        assert open_job.escrow_funded is True

    def test_unmatched_payment_returns_false(self, open_job):
        matched = match_escrow_payment_to_job(
            narration='Random transfer with no reference',
            amount=Decimal('1000'),
            squad_reference='SQUNKNOWN',
        )
        assert matched is False

    def test_transaction_created_on_match(self, open_job, employer_wallet):
        from apps.payments.models import Transaction
        open_job.escrow_reference = 'TXREF002'
        open_job.escrow_funded = False
        open_job.save()

        initial_count = Transaction.objects.count()
        match_escrow_payment_to_job('TXREF002', Decimal('3500'), 'SQX001')
        assert Transaction.objects.count() == initial_count + 1


@pytest.mark.django_db
class TestEscrowRelease:

    def test_worker_receives_95_percent(
        self, open_job, worker, employer,
        worker_wallet, employer_wallet, settings
    ):
        settings.FINANCIAL_PARTNER_MODE = 'simulated'
        settings.PLATFORM_FEE_PERCENT = 5
        settings.ARISE_WALLET_ID = 999   # non-existent, graceful fail

        employer_wallet.escrow_balance = Decimal('3500.00')
        employer_wallet.save()

        initial_worker_balance = worker_wallet.balance
        release_escrow(str(open_job.id), str(worker.id))

        worker_wallet.refresh_from_db()
        expected = Decimal('3500.00') * Decimal('0.95')
        assert worker_wallet.balance == initial_worker_balance + expected

    def test_insufficient_escrow_raises(
        self, open_job, worker, employer,
        worker_wallet, employer_wallet, settings
    ):
        settings.FINANCIAL_PARTNER_MODE = 'simulated'
        employer_wallet.escrow_balance = Decimal('0.00')
        employer_wallet.save()

        with pytest.raises(ValueError, match='Insufficient escrow'):
            release_escrow(str(open_job.id), str(worker.id))

    def test_three_transactions_created(
        self, open_job, worker, employer,
        worker_wallet, employer_wallet, settings
    ):
        from apps.payments.models import Transaction
        settings.FINANCIAL_PARTNER_MODE = 'simulated'
        settings.ARISE_WALLET_ID = 999
        employer_wallet.escrow_balance = Decimal('3500.00')
        employer_wallet.save()

        initial = Transaction.objects.count()
        release_escrow(str(open_job.id), str(worker.id))
        assert Transaction.objects.count() == initial + 3