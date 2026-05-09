import pytest
from decimal import Decimal


@pytest.mark.django_db
class TestListingBrowse:

    def test_feed_is_public(self, api_client, active_listing):
        response = api_client.get('/api/marketplace/listings/')
        assert response.status_code == 200
        data = response.json()['data']
        assert data['total'] >= 1

    def test_filter_by_city(self, api_client, active_listing):
        response = api_client.get('/api/marketplace/listings/?city=Kano')
        data = response.json()['data']
        assert all(l['location_city'] == 'Kano' for l in data['listings'])

    def test_filter_by_category(self, api_client, active_listing, food_category):
        response = api_client.get(f'/api/marketplace/listings/?category={food_category.slug}')
        data = response.json()['data']
        assert data['total'] >= 1

    def test_search_by_title(self, api_client, active_listing):
        response = api_client.get('/api/marketplace/listings/?q=Tomato')
        assert response.json()['data']['total'] >= 1

    def test_search_no_results(self, api_client, active_listing):
        response = api_client.get('/api/marketplace/listings/?q=xyzzyxyzzy')
        assert response.json()['data']['total'] == 0

    def test_detail_is_public(self, api_client, active_listing):
        response = api_client.get(f'/api/marketplace/listings/{active_listing.id}/')
        assert response.status_code == 200
        assert response.json()['data']['title'] == active_listing.title

    def test_removed_listing_not_in_feed(self, api_client, make_listing):
        listing = make_listing(status='removed')
        response = api_client.get('/api/marketplace/listings/')
        ids = [l['id'] for l in response.json()['data']['listings']]
        assert str(listing.id) not in ids


@pytest.mark.django_db
class TestListingCreate:

    def test_create_listing_success(self, trader, trader_wallet, auth_client, food_category):
        client = auth_client(trader)
        response = client.post('/api/marketplace/listings/create/', {
            'title': 'Fresh Peppers',
            'price': '1500',
            'category': food_category.id,
            'location_area': 'Kano Central Market',
            'location_city': 'Kano',
            'unit': 'per kg',
            'quantity_available': 20,
            'price_type': 'negotiable',
        }, format='json')
        assert response.status_code == 201
        assert response.json()['data']['title'] == 'Fresh Peppers'

    def test_price_zero_rejected(self, trader, trader_wallet, auth_client, food_category):
        client = auth_client(trader)
        response = client.post('/api/marketplace/listings/create/', {
            'title': 'Suspicious',
            'price': '0',
            'category': food_category.id,
            'location_area': 'Lagos',
            'location_city': 'Lagos',
        }, format='json')
        assert response.status_code == 400

    def test_max_10_listings_enforced(self, trader, trader_wallet, auth_client, make_listing):
        for i in range(10):
            make_listing(title=f'Item {i}', seller=trader)
        client = auth_client(trader)
        response = client.post('/api/marketplace/listings/create/', {
            'title': 'One Too Many',
            'price': '500',
            'location_area': 'Kano',
            'location_city': 'Kano',
        }, format='json')
        assert response.status_code == 400

    def test_requires_auth(self, api_client):
        response = api_client.post('/api/marketplace/listings/create/', {})
        assert response.status_code == 401


@pytest.mark.django_db
class TestListingUpdate:

    def test_seller_can_update_own_listing(self, trader, trader_wallet, auth_client, active_listing):
        client = auth_client(trader)
        response = client.patch(
            f'/api/marketplace/listings/{active_listing.id}/update/',
            {'price': '2500', 'status': 'paused'},
            format='json'
        )
        assert response.status_code == 200
        active_listing.refresh_from_db()
        assert active_listing.price == Decimal('2500')
        assert active_listing.status == 'paused'

    def test_other_user_cannot_update(self, worker, worker_wallet, auth_client, active_listing):
        client = auth_client(worker)
        response = client.patch(
            f'/api/marketplace/listings/{active_listing.id}/update/',
            {'price': '100'},
            format='json'
        )
        assert response.status_code == 404   # get_object_or_404 with seller=request.user


@pytest.mark.django_db
class TestEnquiries:

    def test_buyer_can_enquire(self, worker, worker_wallet, auth_client, active_listing):
        client = auth_client(worker)
        response = client.post('/api/marketplace/enquiries/', {
            'listing': str(active_listing.id),
            'message': 'Is this still available?',
            'buyer_phone': '+2348011111111',
        }, format='json')
        assert response.status_code == 201

    def test_seller_cannot_enquire_own_listing(self, trader, trader_wallet, auth_client, active_listing):
        client = auth_client(trader)
        response = client.post('/api/marketplace/enquiries/', {
            'listing': str(active_listing.id),
            'message': 'Testing',
        }, format='json')
        assert response.status_code == 400

    def test_enquiry_increments_counter(self, worker, worker_wallet, auth_client, active_listing):
        initial = active_listing.enquiries_count
        client = auth_client(worker)
        client.post('/api/marketplace/enquiries/', {
            'listing': str(active_listing.id),
            'message': 'Interested!',
        }, format='json')
        active_listing.refresh_from_db()
        assert active_listing.enquiries_count == initial + 1

    def test_inactive_listing_enquiry_rejected(self, worker, worker_wallet, auth_client, make_listing):
        listing = make_listing(status='sold')
        client = auth_client(worker)
        response = client.post('/api/marketplace/enquiries/', {
            'listing': str(listing.id),
            'message': 'Still want it',
        }, format='json')
        assert response.status_code == 400


@pytest.mark.django_db
class TestSaveListings:

    def test_save_listing(self, worker, worker_wallet, auth_client, active_listing):
        client = auth_client(worker)
        response = client.post(f'/api/marketplace/listings/{active_listing.id}/save/')
        assert response.status_code == 201
        assert response.json()['data']['saved'] is True

    def test_unsave_listing_toggle(self, worker, worker_wallet, auth_client, active_listing):
        client = auth_client(worker)
        client.post(f'/api/marketplace/listings/{active_listing.id}/save/')
        response = client.post(f'/api/marketplace/listings/{active_listing.id}/save/')
        assert response.json()['data']['saved'] is False