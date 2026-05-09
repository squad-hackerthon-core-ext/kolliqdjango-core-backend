import pytest
from decimal import Decimal
from freezegun import freeze_time


@pytest.mark.django_db
class TestSavings:

    def test_deposit_requires_score(self, worker, worker_wallet, auth_client, make_score):
        make_score(worker, score=5)   # below threshold
        client = auth_client(worker)
        response = client.post('/api/financial/savings/deposit/', {'amount': '500'}, format='json')
        assert response.status_code == 403

    def test_deposit_moves_funds(self, worker, worker_wallet, auth_client, make_score):
        make_score(worker, score=25)
        client = auth_client(worker)
        initial = worker_wallet.balance
        response = client.post('/api/financial/savings/deposit/', {'amount': '1000'}, format='json')
        assert response.status_code == 200
        worker_wallet.refresh_from_db()
        assert worker_wallet.balance == initial - Decimal('1000')

    def test_insufficient_balance_rejected(self, worker, worker_wallet, auth_client, make_score):
        make_score(worker, score=25)
        worker_wallet.balance = Decimal('100.00')
        worker_wallet.save()
        client = auth_client(worker)
        response = client.post('/api/financial/savings/deposit/', {'amount': '5000'}, format='json')
        assert response.status_code == 400

    def test_withdraw_returns_funds(self, worker, worker_wallet, auth_client, make_score):
        from apps.financial_services.models import SavingsPot
        make_score(worker, score=25)
        pot = SavingsPot.objects.create(user=worker, balance=Decimal('3000'))
        client = auth_client(worker)
        response = client.post('/api/financial/savings/withdraw/', {'amount': '1000'}, format='json')
        assert response.status_code == 200
        pot.refresh_from_db()
        assert pot.balance == Decimal('2000')


@pytest.mark.django_db
class TestLoans:

    def test_eligibility_below_score(self, worker, auth_client, make_score):
        make_score(worker, score=30)
        client = auth_client(worker)
        response = client.get('/api/financial/loans/eligibility/')
        assert response.status_code == 200
        assert response.json()['data']['eligible'] is False

    def test_eligibility_above_score(self, worker, auth_client, make_score):
        make_score(worker, score=55)
        client = auth_client(worker)
        response = client.get('/api/financial/loans/eligibility/')
        data = response.json()['data']
        assert data['eligible'] is True
        assert Decimal(data['max_amount']) == Decimal('10000')

    def test_loan_apply_disburses_to_wallet(
        self, worker, worker_wallet, auth_client, make_score, demo_float
    ):
        make_score(worker, score=55)
        client = auth_client(worker)
        initial_balance = worker_wallet.balance
        response = client.post('/api/financial/loans/apply/', {'amount': '5000'}, format='json')
        assert response.status_code == 201
        worker_wallet.refresh_from_db()
        assert worker_wallet.balance == initial_balance + Decimal('5000')

    def test_loan_creates_repayment_schedule(
        self, worker, worker_wallet, auth_client, make_score, demo_float
    ):
        make_score(worker, score=55)
        client = auth_client(worker)
        response = client.post('/api/financial/loans/apply/', {'amount': '4000'}, format='json')
        schedule = response.json()['data']['repayment_schedule']
        assert len(schedule) == 4
        assert all(not s['paid'] for s in schedule)

    def test_double_loan_rejected(
        self, worker, worker_wallet, auth_client, make_score, demo_float
    ):
        make_score(worker, score=55)
        client = auth_client(worker)
        client.post('/api/financial/loans/apply/', {'amount': '5000'}, format='json')
        response = client.post('/api/financial/loans/apply/', {'amount': '2000'}, format='json')
        assert response.status_code == 400

    def test_loan_repayment_updates_status(
        self, worker, worker_wallet, auth_client, make_score, demo_float
    ):
        make_score(worker, score=55)
        client = auth_client(worker)
        apply_resp = client.post('/api/financial/loans/apply/', {'amount': '4000'}, format='json')
        loan_id = apply_resp.json()['data']['loan_id']

        # Repay full amount
        response = client.post('/api/financial/loans/repay/', {
            'loan_id': loan_id,
            'amount': '4200',   # total_repayable at 5%
        }, format='json')
        assert response.status_code == 200
        assert response.json()['data']['loan_status'] == 'repaid'

    def test_demo_float_balance_decreases(
        self, worker, worker_wallet, auth_client, make_score, demo_float
    ):
        make_score(worker, score=55)
        initial = demo_float.balance
        client = auth_client(worker)
        client.post('/api/financial/loans/apply/', {'amount': '5000'}, format='json')
        demo_float.refresh_from_db()
        assert demo_float.balance == initial - Decimal('5000')


@pytest.mark.django_db
class TestInsurance:

    def test_activate_requires_score_70(self, worker, worker_wallet, auth_client, make_score):
        make_score(worker, score=65)
        client = auth_client(worker)
        response = client.post('/api/financial/insurance/activate/')
        assert response.status_code == 403

    def test_activate_deducts_first_premium(self, worker, worker_wallet, auth_client, make_score):
        make_score(worker, score=75)
        initial = worker_wallet.balance
        client = auth_client(worker)
        response = client.post('/api/financial/insurance/activate/')
        assert response.status_code == 201
        worker_wallet.refresh_from_db()
        assert worker_wallet.balance == initial - Decimal('200')   # ₦200 first day

    def test_claim_auto_approved_under_5000(
        self, worker, worker_wallet, auth_client, make_score, demo_float
    ):
        from apps.financial_services.models import InsurancePolicy
        make_score(worker, score=75)
        InsurancePolicy.objects.create(
            user=worker, daily_premium=Decimal('200'),
            coverage_limit=Decimal('50000'), status='active'
        )
        client = auth_client(worker)
        response = client.post('/api/financial/insurance/claim/', {
            'days_missed': 2,
            'reason': 'I was sick',
        }, format='json')
        assert response.status_code == 201
        assert response.json()['data']['status'] == 'auto_approved'

    def test_claim_manual_review_above_5000(
        self, worker, worker_wallet, auth_client, make_score, demo_float
    ):
        from apps.financial_services.models import InsurancePolicy
        make_score(worker, score=75)
        InsurancePolicy.objects.create(
            user=worker, daily_premium=Decimal('200'),
            coverage_limit=Decimal('50000'), status='active'
        )
        client = auth_client(worker)
        # 4 days × (50000/30) = ₦6,666 > ₦5,000 threshold
        response = client.post('/api/financial/insurance/claim/', {
            'days_missed': 4,
            'reason': 'Market was closed',
        }, format='json')
        assert response.status_code == 201
        assert response.json()['data']['status'] == 'manual_review'