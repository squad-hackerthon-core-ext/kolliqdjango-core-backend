import pytest
from decimal import Decimal
from apps.scoring.engine import (
    calculate_score, get_unlocked_services, get_score_summary,
    SAVINGS_UNLOCK_SCORE, INSURANCE_UNLOCK_SCORE, LOAN_UNLOCK_SCORE,
)


@pytest.mark.django_db
class TestScoringEngine:

    def test_new_user_scores_10(self, worker):
        result = calculate_score(worker)
        assert result['score'] == 10
        assert result['breakdown']['base'] == 10

    def test_completed_gig_adds_points(self, worker, employer, open_job, worker_wallet, employer_wallet):
        from apps.jobs.models import JobApplication
        from django.utils import timezone
        JobApplication.objects.create(
            job=open_job,
            worker=worker,
            status='completed',
            completed_at=timezone.now(),
        )
        result = calculate_score(worker)
        assert result['breakdown']['gigs_completed'] == 5   # 1 gig × 5 pts
        assert result['score'] == 15

    def test_transaction_adds_points(self, worker, worker_wallet):
        from apps.payments.models import Transaction
        for i in range(3):
            Transaction.objects.create(
                user=worker,
                transaction_type='credit',
                amount=Decimal('1000'),
                status='success',
                description=f'Test payment {i}',
            )
        result = calculate_score(worker)
        assert result['breakdown']['transactions_recorded'] == 6  # 3 × 2 pts
        assert result['score'] == 16

    def test_score_caps_at_100(self, worker, worker_wallet):
        from apps.payments.models import Transaction
        # Flood with transactions to try to exceed cap
        for i in range(100):
            Transaction.objects.create(
                user=worker, transaction_type='credit',
                amount=Decimal('100'), status='success',
            )
        result = calculate_score(worker)
        assert result['score'] == 100

    def test_savings_unlocks_at_threshold(self):
        assert 'micro_savings' not in get_unlocked_services(19)
        assert 'micro_savings' in get_unlocked_services(SAVINGS_UNLOCK_SCORE)

    def test_insurance_unlocks_at_threshold(self):
        assert 'micro_insurance' not in get_unlocked_services(39)
        assert 'micro_insurance' in get_unlocked_services(INSURANCE_UNLOCK_SCORE)

    def test_loan_unlocks_at_threshold(self):
        assert 'micro_loan' not in get_unlocked_services(59)
        assert 'micro_loan' in get_unlocked_services(LOAN_UNLOCK_SCORE)

    def test_score_summary_tiers(self):
        assert get_score_summary(5)['tier'] == 'starter'
        assert get_score_summary(25)['tier'] == 'active'
        assert get_score_summary(55)['tier'] == 'trusted'
        assert get_score_summary(72)['tier'] == 'established'
        assert get_score_summary(95)['tier'] == 'champion'

    def test_next_unlock_returned(self):
        summary = get_score_summary(15)
        assert summary['next_unlock']['service'] == 'micro_savings'
        assert summary['next_unlock']['points_needed'] == 5

    def test_no_next_unlock_at_max(self):
        summary = get_score_summary(100)
        assert summary['next_unlock'] is None