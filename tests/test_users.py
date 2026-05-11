import pytest
from django.urls import reverse
from decimal import Decimal


@pytest.mark.django_db
class TestUserCreate:

    def test_create_worker_success(self, api_client):
        url = '/api/users/create/'
        data = {
            'phone': '08012345678',
            'role': 'worker',
            'full_name': 'Tunde Adeyemi',
            'skills': ['delivery'],
            'channel': 'app',
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == 201
        body = response.json()
        assert body['success'] is True
        assert 'access_token' in body['data']
        assert body['data']['role'] == 'worker'

    def test_phone_normalised_to_plus234(self, api_client):
        url = '/api/users/create/'
        data = {'phone': '08099998888', 'role': 'worker'}
        response = api_client.post(url, data, format='json')
        assert response.status_code == 201
        assert response.json()['data']['phone'] == '+2348099998888'

    
    def test_create_user_idempotent(self, api_client, worker):
        """Calling create twice with same phone returns existing user, not error."""
        url = '/api/users/create/'
        data = {'phone': worker.phone, 'role': 'worker'}
        
        r1 = api_client.post(url, data, format='json')
        r2 = api_client.post(url, data, format='json')
        
        # Both requests should be successful
        assert r1.status_code == 200
        assert r2.status_code == 200
        
        # Check success flag
        assert r1.json()['success'] is True
        assert r2.json()['success'] is True
        
        # Check same user returned (either directly or in 'data' field)
        r1_data = r1.json()
        r2_data = r2.json()
        
        # If response has 'data' wrapper
        if 'data' in r1_data:
            assert r1_data['data']['phone'] == r2_data['data']['phone']
            # Optionally check user ID if present
            if 'id' in r1_data['data']:
                assert r1_data['data']['id'] == r2_data['data']['id']
        else:
            # If response is the user object directly
            assert r1_data['phone'] == r2_data['phone']

    def test_invalid_phone_rejected(self, api_client):
        url = '/api/users/create/'
        data = {'phone': 'not-a-phone', 'role': 'worker'}
        response = api_client.post(url, data, format='json')
        assert response.status_code == 400
        assert response.json()['success'] is False

    def test_profile_requires_auth(self, api_client):
        response = api_client.get('/api/users/profile/')
        assert response.status_code == 401

    def test_profile_returns_score_and_balance(self, worker, worker_score, worker_wallet, auth_client):
        client = auth_client(worker)
        response = client.get('/api/users/profile/')
        assert response.status_code == 200
        data = response.json()['data']
        assert data['economic_score'] == 10
        assert data['wallet_balance'] == '5000.00'

    def test_onboarding_updates_user(self, worker, auth_client):
        client = auth_client(worker)
        response = client.patch('/api/users/onboarding/', {
            'full_name': 'Tunde Updated',
            'location_area': 'Victoria Island',
            'skills': ['delivery', 'cleaning'],
        }, format='json')
        assert response.status_code == 200
        worker.refresh_from_db()
        assert worker.full_name == 'Tunde Updated'
        assert 'cleaning' in worker.skills