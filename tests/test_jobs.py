import pytest
from decimal import Decimal
from django.utils import timezone


@pytest.mark.django_db
class TestJobFeed:

    def test_feed_requires_auth(self, api_client):
        response = api_client.get('/api/jobs/feed/')
        assert response.status_code == 401

    def test_employer_cannot_see_feed(self, employer, auth_client):
        client = auth_client(employer)
        response = client.get('/api/jobs/feed/')
        assert response.status_code == 403

    def test_feed_returns_matched_jobs(self, worker, worker_wallet, open_job, auth_client):
        client = auth_client(worker)
        response = client.get('/api/jobs/feed/')
        assert response.status_code == 200
        data = response.json()['data']
        assert data['count'] >= 1
        assert data['jobs'][0]['skill_required'] == 'delivery'

    def test_feed_excludes_unfunded_jobs(self, worker, auth_client, make_job):
        make_job(escrow_funded=False)
        client = auth_client(worker)
        response = client.get('/api/jobs/feed/')
        data = response.json()['data']
        # Unfunded job should not appear
        funded_only = all(j['escrow_funded'] for j in data['jobs'])
        assert funded_only

    def test_feed_excludes_wrong_skill(self, worker, auth_client, make_job):
        make_job(skill_required='cooking')  # worker has delivery skill
        client = auth_client(worker)
        response = client.get('/api/jobs/feed/')
        # Cooking job should not appear for delivery worker
        job_skills = [j['skill_required'] for j in response.json()['data']['jobs']]
        assert 'cooking' not in job_skills


@pytest.mark.django_db
class TestJobAccept:

    def test_worker_accepts_job(self, worker, worker_wallet, open_job, auth_client):
        client = auth_client(worker)
        response = client.post('/api/jobs/accept/', {'job_id': str(open_job.id)}, format='json')
        assert response.status_code == 201
        data = response.json()['data']
        assert 'application_id' in data

    def test_double_accept_rejected(self, worker, worker_wallet, open_job, auth_client):
        client = auth_client(worker)
        client.post('/api/jobs/accept/', {'job_id': str(open_job.id)}, format='json')
        response = client.post('/api/jobs/accept/', {'job_id': str(open_job.id)}, format='json')
        assert response.status_code == 409

    def test_employer_cannot_accept_job(self, employer, open_job, auth_client, employer_wallet):
        client = auth_client(employer)
        response = client.post('/api/jobs/accept/', {'job_id': str(open_job.id)}, format='json')
        assert response.status_code == 403

    def test_unfunded_job_cannot_be_accepted(self, worker, auth_client, make_job, worker_wallet):
        job = make_job(escrow_funded=False)
        client = auth_client(worker)
        response = client.post('/api/jobs/accept/', {'job_id': str(job.id)}, format='json')
        assert response.status_code == 409


@pytest.mark.django_db
class TestJobComplete:

    def test_employer_completes_job(
        self, worker, employer, open_job,
        worker_wallet, employer_wallet, auth_client
    ):
        from apps.jobs.models import JobApplication

        # Worker accepts job first
        JobApplication.objects.create(
            job=open_job, worker=worker, status='accepted'
        )
        open_job.status = 'in_progress'
        open_job.escrow_funded = True
        employer_wallet.escrow_balance = Decimal('3500.00')
        employer_wallet.save()
        open_job.save()

        client = auth_client(employer)
        response = client.post('/api/jobs/complete/', {
            'job_id': str(open_job.id),
            'worker_id': str(worker.id),
        }, format='json')
        assert response.status_code == 200
        data = response.json()['data']
        assert data['workers_paid'] == 1

    def test_worker_cannot_confirm_complete(self, worker, open_job, auth_client, worker_wallet):
        client = auth_client(worker)
        response = client.post('/api/jobs/complete/', {'job_id': str(open_job.id)}, format='json')
        assert response.status_code == 403


@pytest.mark.django_db
class TestRating:

    def test_employer_rates_worker(
        self, worker, employer, open_job,
        worker_wallet, employer_wallet, auth_client
    ):
        from apps.jobs.models import JobApplication
        JobApplication.objects.create(job=open_job, worker=worker, status='completed')

        client = auth_client(employer)
        response = client.post('/api/jobs/rate/', {
            'to_user': str(worker.id),
            'job': str(open_job.id),
            'stars': 5,
            'comment': 'Very reliable!',
        }, format='json')
        assert response.status_code == 201

    def test_cannot_rate_yourself(self, worker, open_job, worker_wallet, auth_client):
        from apps.jobs.models import JobApplication
        JobApplication.objects.create(job=open_job, worker=worker, status='completed')

        client = auth_client(worker)
        response = client.post('/api/jobs/rate/', {
            'to_user': str(worker.id),
            'job': str(open_job.id),
            'stars': 5,
        }, format='json')
        assert response.status_code == 400

    def test_invalid_stars_rejected(self, employer, worker, open_job, employer_wallet, auth_client):
        from apps.jobs.models import JobApplication
        JobApplication.objects.create(job=open_job, worker=worker, status='completed')

        client = auth_client(employer)
        response = client.post('/api/jobs/rate/', {
            'to_user': str(worker.id),
            'job': str(open_job.id),
            'stars': 6,
        }, format='json')
        assert response.status_code == 400