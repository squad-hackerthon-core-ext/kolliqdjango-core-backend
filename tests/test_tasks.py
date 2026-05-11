# tests/test_tasks.py
# Tests for Celery tasks — currently 0-19% coverage on all task files
# These push overall coverage past 75%

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock


# ══════════════════════════════════════════════════════════════════
# WALLET TASKS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWalletTasks:

    def test_create_wallet_for_user_success(self, worker, settings):
        """Squad VA creation succeeds — wallet gets account number."""
        from apps.wallets.tasks import create_wallet_for_user
        from apps.wallets.models import Wallet

        settings.CELERY_TASK_ALWAYS_EAGER = True

        mock_result = {
            'virtual_account_number': '0812345678',
            'bank_name': 'GTBank',
            'customer_identifier': str(worker.id),
        }
        with patch('apps.wallets.tasks.SquadService') as MockSquad:
            MockSquad.return_value.create_virtual_account.return_value = mock_result
            create_wallet_for_user(str(worker.id))

        wallet = Wallet.objects.get(user=worker)
        assert wallet.squad_account_number == '0812345678'
        assert wallet.squad_creation_status == 'created'

    def test_create_wallet_squad_failure_marks_failed(self, worker, settings):
        """Squad API failure marks wallet as failed, retries."""
        from apps.wallets.tasks import create_wallet_for_user
        from apps.wallets.models import Wallet
        from services.squad import SquadAPIError

        settings.CELERY_TASK_ALWAYS_EAGER = True

        Wallet.objects.get_or_create(user=worker)

        with patch('apps.wallets.tasks.SquadService') as MockSquad:
            MockSquad.return_value.create_virtual_account.side_effect = (
                SquadAPIError('Network error')
            )
            with pytest.raises(Exception):
                create_wallet_for_user(str(worker.id))

        wallet = Wallet.objects.get(user=worker)
        assert wallet.squad_creation_status == 'failed'

    def test_create_wallet_idempotent(self, worker, settings):
        """Calling create_wallet twice doesn't duplicate the wallet."""
        from apps.wallets.tasks import create_wallet_for_user
        from apps.wallets.models import Wallet

        settings.CELERY_TASK_ALWAYS_EAGER = True

        # Pre-create wallet as already provisioned
        Wallet.objects.update_or_create(
            user=worker,
            defaults={
                'squad_account_number': '0999999999',
                'squad_creation_status': 'created',
            }
        )

        with patch('apps.wallets.tasks.SquadService') as MockSquad:
            create_wallet_for_user(str(worker.id))
            # Should NOT call Squad again
            MockSquad.return_value.create_virtual_account.assert_not_called()

    def test_create_wallet_nonexistent_user(self, settings):
        """Gracefully handles missing user ID."""
        from apps.wallets.tasks import create_wallet_for_user
        settings.CELERY_TASK_ALWAYS_EAGER = True
        # Should not raise — just log and return
        create_wallet_for_user('00000000-0000-0000-0000-000000000000')


# ══════════════════════════════════════════════════════════════════
# SCORING TASKS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestScoringTasks:

    def test_initialise_score_creates_record(self, worker, settings):
        """initialise_score_for_user creates EconomicIdentityScore at 10."""
        from apps.scoring.tasks import initialise_score_for_user
        from apps.scoring.models import EconomicIdentityScore

        settings.CELERY_TASK_ALWAYS_EAGER = True

        initialise_score_for_user(str(worker.id))

        score = EconomicIdentityScore.objects.get(user=worker)
        assert score.score == 10

    def test_initialise_score_idempotent(self, worker, make_score, settings):
        """Calling initialise twice doesn't reset an existing score."""
        from apps.scoring.tasks import initialise_score_for_user

        settings.CELERY_TASK_ALWAYS_EAGER = True
        make_score(worker, score=55)

        initialise_score_for_user(str(worker.id))

        from apps.scoring.models import EconomicIdentityScore
        score = EconomicIdentityScore.objects.get(user=worker)
        assert score.score == 55  # not reset to 10

    def test_recalculate_score_updates_record(
        self, worker, worker_wallet, make_score, settings
    ):
        """recalculate_score reads real activity and updates score."""
        from apps.scoring.tasks import recalculate_score
        from apps.payments.models import Transaction

        settings.CELERY_TASK_ALWAYS_EAGER = True
        make_score(worker, score=10)

        # Add some credit transactions
        for i in range(5):
            Transaction.objects.create(
                user=worker,
                transaction_type='credit',
                amount=Decimal('1000'),
                status='success',
                description=f'Test {i}',
            )

        with patch('apps.scoring.tasks.ATService'):
            recalculate_score(str(worker.id))

        from apps.scoring.models import EconomicIdentityScore
        score = EconomicIdentityScore.objects.get(user=worker)
        assert score.score > 10  # grew from activity

    def test_recalculate_score_sets_unlock_flags(
        self, worker, worker_wallet, make_score, settings
    ):
        """Score above thresholds sets savings/loan/insurance unlock flags."""
        from apps.scoring.tasks import recalculate_score
        from apps.scoring.models import EconomicIdentityScore
        from apps.payments.models import Transaction

        settings.CELERY_TASK_ALWAYS_EAGER = True
        make_score(worker, score=10)

        # Add enough transactions to push past loan threshold (50)
        for i in range(25):
            Transaction.objects.create(
                user=worker,
                transaction_type='credit',
                amount=Decimal('500'),
                status='success',
            )

        with patch('apps.scoring.tasks.ATService'):
            recalculate_score(str(worker.id))

        score_obj = EconomicIdentityScore.objects.get(user=worker)
        assert score_obj.savings_unlocked is True

    def test_recalculate_score_nonexistent_user(self, settings):
        """Gracefully handles missing user ID."""
        from apps.scoring.tasks import recalculate_score
        settings.CELERY_TASK_ALWAYS_EAGER = True
        recalculate_score('00000000-0000-0000-0000-000000000000')


# ══════════════════════════════════════════════════════════════════
# PAYMENT TASKS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPaymentTasks:

    def test_process_squad_webhook_escrow_payment(
        self, open_job, employer, employer_wallet, settings
    ):
        """Webhook for escrow VA payment matches job and funds it."""
        from apps.payments.tasks import process_squad_webhook

        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT = '0123456789'

        open_job.escrow_reference = 'TESTREF999'
        open_job.escrow_funded = False
        open_job.save()

        payload = {
            'Event': 'virtual_account.payment',
            'Body': {
                'virtual_account_number': '0123456789',
                'amount': 350000,          # kobo
                'transaction_ref': 'SQ001',
                'transaction_remarks': 'Payment TESTREF999 delivery job',
                'sender_name': 'ALHAJI MUSA',
            }
        }

        with patch('apps.jobs.tasks.trigger_job_matching_notifications'):
            process_squad_webhook(payload)

        open_job.refresh_from_db()
        assert open_job.escrow_funded is True

    def test_process_squad_webhook_user_va_payment(
        self, trader, trader_wallet, settings
    ):
        """Webhook for user's personal VA credits their wallet."""
        from apps.payments.tasks import process_squad_webhook
        from apps.wallets.models import Wallet

        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.KOLLIQ_ESCROW_VIRTUAL_ACCOUNT = '0000000000'

        trader_wallet.squad_account_number = '9876543210'
        trader_wallet.save()

        initial_balance = trader_wallet.balance

        payload = {
            'Event': 'virtual_account.payment',
            'Body': {
                'virtual_account_number': '9876543210',
                'amount': 200000,    # ₦2,000 in kobo
                'transaction_ref': 'SQ002',
                'transaction_remarks': 'Payment for tomatoes',
                'sender_name': 'EMEKA CUSTOMER',
            }
        }

        with patch('apps.scoring.tasks.recalculate_score'):
            with patch('services.notifications.notify_trader_payment_received'):
                process_squad_webhook(payload)

        trader_wallet.refresh_from_db()
        assert trader_wallet.balance == initial_balance + Decimal('2000.00')

    def test_process_squad_webhook_unknown_event(self, settings):
        """Unknown event type logged but does not raise."""
        from apps.payments.tasks import process_squad_webhook
        settings.CELERY_TASK_ALWAYS_EAGER = True
        payload = {'Event': 'unknown.event.type', 'Body': {}}
        process_squad_webhook(payload)  # should not raise

    def test_release_escrow_task_calls_escrow(
        self, open_job, worker, employer,
        worker_wallet, employer_wallet, settings
    ):
        """release_escrow_for_job task calls release_escrow correctly."""
        from apps.payments.tasks import release_escrow_for_job

        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.FINANCIAL_PARTNER_MODE = 'simulated'
        settings.ARISE_WALLET_ID = 99999

        employer_wallet.escrow_balance = Decimal('3500.00')
        employer_wallet.save()

        release_escrow_for_job(str(open_job.id), str(worker.id))

        worker_wallet.refresh_from_db()
        assert worker_wallet.balance == Decimal('5000.00') + Decimal('3325.00')


# ══════════════════════════════════════════════════════════════════
# JOB TASKS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestJobTasks:

    def test_notify_employer_worker_accepted(
        self, worker, employer, open_job,
        worker_wallet, employer_wallet, settings
    ):
        """Employer SMS sent when worker accepts job."""
        from apps.jobs.tasks import notify_employer_worker_accepted
        from apps.jobs.models import JobApplication

        settings.CELERY_TASK_ALWAYS_EAGER = True

        app = JobApplication.objects.create(
            job=open_job, worker=worker, status='accepted'
        )

        with patch('services.africas_talking.ATService.send_sms') as mock_sms:
            notify_employer_worker_accepted(str(app.id))
            mock_sms.assert_called_once()
            call_args = mock_sms.call_args
            assert employer.phone in call_args[0]

    def test_trigger_job_matching_notifications(
        self, open_job, worker, employer,
        worker_wallet, employer_wallet, settings
    ):
        """Workers with matching skills get SMS when job goes live."""
        from apps.jobs.tasks import trigger_job_matching_notifications

        settings.CELERY_TASK_ALWAYS_EAGER = True

        with patch('services.africas_talking.ATService.send_sms') as mock_sms:
            trigger_job_matching_notifications(str(open_job.id))
            # Worker has delivery skill matching the job
            assert mock_sms.called


# ══════════════════════════════════════════════════════════════════
# MARKETPLACE TASKS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMarketplaceTasks:

    def test_notify_seller_new_enquiry(
        self, trader, trader_wallet, worker, worker_wallet,
        active_listing, settings
    ):
        """Seller gets SMS when buyer submits enquiry."""
        from apps.marketplace.tasks import notify_seller_new_enquiry
        from apps.marketplace.models import Enquiry

        settings.CELERY_TASK_ALWAYS_EAGER = True

        enquiry = Enquiry.objects.create(
            listing=active_listing,
            buyer=worker,
            buyer_phone=worker.phone,
            message='Is this still available?',
        )

        with patch('services.africas_talking.ATService.send_sms') as mock_sms:
            notify_seller_new_enquiry(str(enquiry.id))
            mock_sms.assert_called_once()
            call_args = mock_sms.call_args
            assert trader.phone in call_args[0]

    def test_expire_old_listings(self, make_listing, settings):
        """Listings older than 30 days are paused."""
        from apps.marketplace.tasks import expire_old_listings
        from django.utils import timezone
        from datetime import timedelta

        settings.CELERY_TASK_ALWAYS_EAGER = True

        old_listing = make_listing(status='active')
        # Manually set created_at to 31 days ago
        old_listing.__class__.objects.filter(id=old_listing.id).update(
            created_at=timezone.now() - timedelta(days=31)
        )

        expire_old_listings()

        old_listing.refresh_from_db()
        assert old_listing.status == 'paused'

    def test_increment_listing_views(self, active_listing, settings):
        """View count increments correctly."""
        from apps.marketplace.tasks import increment_listing_views

        settings.CELERY_TASK_ALWAYS_EAGER = True
        initial_views = active_listing.views_count

        increment_listing_views(str(active_listing.id))

        active_listing.refresh_from_db()
        assert active_listing.views_count == initial_views + 1


# ══════════════════════════════════════════════════════════════════
# FINANCIAL SERVICES TASKS
# ══════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFinancialTasks:

    def test_accrue_daily_savings_interest(self, worker, worker_wallet, settings):
        """Daily interest added to savings pot balance."""
        from apps.financial_services.tasks import accrue_daily_savings_interest
        from apps.financial_services.models import SavingsPot

        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.SAVINGS_ANNUAL_INTEREST_RATE = 5.0

        pot = SavingsPot.objects.create(
            user=worker,
            balance=Decimal('10000.00'),
        )

        accrue_daily_savings_interest()

        pot.refresh_from_db()
        # Daily rate = 5/365/100 ≈ 0.000137 → ₦10,000 * 0.000137 ≈ ₦1.37
        assert pot.balance > Decimal('10000.00')
        assert pot.total_interest_earned > Decimal('0')

    def test_deduct_daily_insurance_premiums_active(
        self, worker, worker_wallet, settings
    ):
        """Premium deducted from active policy holder wallet."""
        from apps.financial_services.tasks import deduct_daily_insurance_premiums
        from apps.financial_services.models import InsurancePolicy

        settings.CELERY_TASK_ALWAYS_EAGER = True

        InsurancePolicy.objects.create(
            user=worker,
            daily_premium=Decimal('200'),
            coverage_limit=Decimal('50000'),
            status='active',
        )

        initial_balance = worker_wallet.balance

        with patch('services.africas_talking.ATService.send_sms'):
            deduct_daily_insurance_premiums()

        worker_wallet.refresh_from_db()
        assert worker_wallet.balance == initial_balance - Decimal('200')

    def test_deduct_daily_insurance_pauses_when_wallet_empty(
        self, worker, worker_wallet, settings
    ):
        """Policy pauses when wallet has insufficient balance."""
        from apps.financial_services.tasks import deduct_daily_insurance_premiums
        from apps.financial_services.models import InsurancePolicy

        settings.CELERY_TASK_ALWAYS_EAGER = True

        worker_wallet.balance = Decimal('100.00')  # less than ₦200 premium
        worker_wallet.save()

        policy = InsurancePolicy.objects.create(
            user=worker,
            daily_premium=Decimal('200'),
            coverage_limit=Decimal('50000'),
            status='active',
        )

        with patch('services.africas_talking.ATService.send_sms'):
            deduct_daily_insurance_premiums()

        policy.refresh_from_db()
        assert policy.status == 'paused'

    def test_process_weekly_loan_repayments_success(
        self, worker, worker_wallet, demo_float, settings
    ):
        """Weekly installment auto-deducted from wallet."""
        from apps.financial_services.tasks import process_weekly_loan_repayments
        from apps.financial_services.models import Loan
        from django.utils import timezone
        from datetime import timedelta

        settings.CELERY_TASK_ALWAYS_EAGER = True

        today = timezone.now().date()
        yesterday = (today - timedelta(days=1)).isoformat()

        loan = Loan.objects.create(
            user=worker,
            amount=Decimal('10000'),
            total_repayable=Decimal('10500'),
            amount_repaid=Decimal('0'),
            status='active',
            funding_source='demo_float',
            repayment_schedule=[
                {
                    'week': 1,
                    'due_date': yesterday,
                    'amount': '2625.00',
                    'paid': False,
                },
                {
                    'week': 2,
                    'due_date': (today + timedelta(days=6)).isoformat(),
                    'amount': '2625.00',
                    'paid': False,
                },
            ]
        )

        initial_balance = worker_wallet.balance

        with patch('services.africas_talking.ATService.send_sms'):
            with patch('apps.scoring.tasks.recalculate_score'):
                process_weekly_loan_repayments()

        worker_wallet.refresh_from_db()
        loan.refresh_from_db()

        assert worker_wallet.balance == initial_balance - Decimal('2625.00')
        assert loan.repayment_schedule[0]['paid'] is True

    def test_fraud_detection_sweep_flags_early_loan(
        self, worker, worker_wallet, demo_float, make_score, settings
    ):
        """User who applies for loan within 24h of registration gets flagged."""
        from apps.financial_services.tasks import fraud_detection_sweep
        from apps.financial_services.models import Loan
        from django.utils import timezone

        settings.CELERY_TASK_ALWAYS_EAGER = True

        make_score(worker, score=55)

        # Create loan for brand new account (created_at is very recent by default)
        Loan.objects.create(
            user=worker,
            amount=Decimal('5000'),
            total_repayable=Decimal('5250'),
            status='active',
            funding_source='demo_float',
        )

        fraud_detection_sweep()

        worker.refresh_from_db()
        assert worker.is_flagged is True