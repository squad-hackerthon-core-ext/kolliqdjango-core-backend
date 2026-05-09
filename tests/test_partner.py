import pytest
from decimal import Decimal


@pytest.mark.django_db
class TestPartnerAPI:

    PARTNER_HEADER = {'HTTP_X_PARTNER_SECRET': 'change-me-in-production'}

    def test_summary_requires_partner_secret(self, auth_client, employer, employer_wallet):
        client = auth_client(employer)
        # No secret header
        response = client.get('/api/partner/summary/')
        assert response.status_code == 401

    def test_summary_returns_platform_stats(
        self, auth_client, employer, employer_wallet, worker, worker_wallet, make_score, settings
    ):
        settings.PARTNER_API_SECRET = 'change-me-in-production'
        make_score(worker, score=65)
        client = auth_client(employer)
        response = client.get(
            '/api/partner/summary/',
            HTTP_X_PARTNER_SECRET='change-me-in-production'
        )
        assert response.status_code == 200
        data = response.json()['data']
        assert 'score_distribution' in data
        assert 'financial_services' in data
        assert data['platform']['financial_partner_mode'] == 'simulated'

    def test_eligible_borrowers_anonymised(
        self, auth_client, employer, employer_wallet, worker, worker_wallet, make_score, settings
    ):
        settings.PARTNER_API_SECRET = 'change-me-in-production'
        settings.LOAN_SCORE_THRESHOLD = 50
        make_score(worker, score=65, loan_unlocked=True)
        client = auth_client(employer)
        response = client.get(
            '/api/partner/eligible-borrowers/',
            HTTP_X_PARTNER_SECRET='change-me-in-production'
        )
        assert response.status_code == 200
        borrowers = response.json()['data']['eligible_borrowers']
        # IDs must be truncated — full UUIDs are 36 chars
        if borrowers:
            assert len(borrowers[0]['anonymous_id']) == 8

    def test_score_report_returns_full_history(
        self, auth_client, employer, employer_wallet, worker, worker_wallet, make_score, settings
    ):
        settings.PARTNER_API_SECRET = 'change-me-in-production'
        make_score(worker, score=55)
        client = auth_client(employer)
        response = client.get(
            f'/api/partner/score-report/{worker.id}/',
            HTTP_X_PARTNER_SECRET='change-me-in-production'
        )
        assert response.status_code == 200
        data = response.json()['data']
        assert 'score' in data
        assert 'credit_history' in data
        assert 'activity' in data