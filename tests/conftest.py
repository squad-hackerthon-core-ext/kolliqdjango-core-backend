"""
Shared pytest fixtures for all Kolliq tests.
Uses factory_boy for clean test data, freezegun for time control.
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import connection

User = get_user_model()

@pytest.fixture(autouse=True)
def ensure_db_connection():
    """Ensure database connection is alive before each test"""
    connection.ensure_connection()
    yield
    # Don't close here - let Django handle it

# ── API client helpers ────────────────────────────────────────────

@pytest.fixture(autouse=True)
def celery_eager(settings):
    """Force Celery tasks to run synchronously in tests."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    yield


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client):
    """Returns a factory: call auth_client(user) → authenticated APIClient."""
    def _auth(user):
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        return api_client
    return _auth


# ── User fixtures ────────────────────────────────────────────────

@pytest.fixture
def make_user(db):
    """Factory for creating users with sensible defaults."""
    def _make(
        phone='+2348012345678',
        role='worker',
        full_name='Test User',
        location_city='Lagos',
        location_area='Surulere',
        location_lat=Decimal('6.5009'),
        location_lng=Decimal('3.3564'),
        skills=None,
        **kwargs
    ):
        return User.objects.create(
            phone=phone,
            role=role,
            full_name=full_name,
            location_city=location_city,
            location_area=location_area,
            location_lat=location_lat,
            location_lng=location_lng,
            skills=skills or (['delivery'] if role == 'worker' else []),
            **kwargs
        )
    return _make


@pytest.fixture
def worker(make_user):
    return make_user(
        phone='+2348011111111',
        role='worker',
        full_name='Tunde Adeyemi',
        skills=['delivery'],
        has_vehicle=True,
        vehicle_type='bike',
    )


@pytest.fixture
def trader(make_user):
    return make_user(
        phone='+2347022222222',
        role='trader',
        full_name='Amina Bello',
        location_city='Kano',
        location_area='Kano Central Market',
        trade_category='food',
        market_name='Kano Central Market',
        skills=[],
    )


@pytest.fixture
def employer(make_user):
    return make_user(
        phone='+2348033333333',
        role='employer',
        full_name='Alhaji Musa',
        business_name='Musa Stores',
        skills=[],
    )


# ── Wallet fixtures ──────────────────────────────────────────────

@pytest.fixture
def make_wallet(db):
    from apps.wallets.models import Wallet
    def _make(user, balance=Decimal('0.00'), squad_account_number='1234567890'):
        wallet, _ = Wallet.objects.get_or_create(
            user=user,
            defaults={
                'balance': balance,
                'squad_account_number': squad_account_number,
                'squad_creation_status': 'created',
            }
        )
        if wallet.balance != balance:
            wallet.balance = balance
            wallet.save()
        return wallet
    return _make


@pytest.fixture
def worker_wallet(worker, make_wallet):
    return make_wallet(worker, balance=Decimal('5000.00'))


@pytest.fixture
def employer_wallet(employer, make_wallet):
    return make_wallet(employer, balance=Decimal('50000.00'))


@pytest.fixture
def trader_wallet(trader, make_wallet):
    return make_wallet(trader, balance=Decimal('10000.00'))


# ── Score fixtures ───────────────────────────────────────────────

@pytest.fixture
def make_score(db):
    from apps.scoring.models import EconomicIdentityScore
    def _make(user, score=10, **kwargs):
        obj, _ = EconomicIdentityScore.objects.get_or_create(
            user=user,
            defaults={'score': score, 'breakdown': {'base': score}, **kwargs}
        )
        if obj.score != score:
            obj.score = score
            obj.save()
        return obj
    return _make


@pytest.fixture
def worker_score(worker, make_score):
    return make_score(worker, score=10)


# ── Job fixtures ─────────────────────────────────────────────────

@pytest.fixture
def make_job(db, employer, employer_wallet):
    from apps.jobs.models import Job
    def _make(
        title='Delivery Rider Needed',
        skill_required='delivery',
        pay=Decimal('3500.00'),
        location_area='Surulere, Lagos',
        location_city='Lagos',
        location_lat=Decimal('6.5009'),
        location_lng=Decimal('3.3564'),
        status='open',
        escrow_funded=True,
        workers_needed=1,
        **kwargs
    ):
        return Job.objects.create(
            employer=employer,
            title=title,
            skill_required=skill_required,
            pay_per_worker=pay,
            location_area=location_area,
            location_city=location_city,
            location_lat=location_lat,
            location_lng=location_lng,
            status=status,
            escrow_funded=escrow_funded,
            workers_needed=workers_needed,
            **kwargs
        )
    return _make


@pytest.fixture
def open_job(make_job):
    return make_job()


# ── Financial fixtures ───────────────────────────────────────────

@pytest.fixture
def demo_float(db):
    from apps.financial_services.models import DemoFloat
    obj, _ = DemoFloat.objects.get_or_create(
        id=1,
        defaults={'balance': Decimal('500000.00')}
    )
    if obj.balance < Decimal('500000.00'):
        obj.balance = Decimal('500000.00')
        obj.save()
    return obj


# ── Marketplace fixtures ─────────────────────────────────────────

@pytest.fixture
def make_category(db):
    from apps.marketplace.models import Category
    def _make(name='Food & Groceries', slug='food-groceries', icon='🍅'):
        cat, _ = Category.objects.get_or_create(
            slug=slug, defaults={'name': name, 'icon': icon}
        )
        return cat
    return _make


@pytest.fixture
def food_category(make_category):
    return make_category()


@pytest.fixture
def make_listing(db, trader, trader_wallet, food_category):
    from apps.marketplace.models import Listing
    def _make(
        title='Fresh Tomatoes',
        price=Decimal('2000.00'),
        status='active',
        seller=None,
        **kwargs
    ):
        return Listing.objects.create(
            seller=seller or trader,
            category=food_category,
            title=title,
            price=price,
            price_type='fixed',
            location_area='Kano Central Market',
            location_city='Kano',
            status=status,
            unit='per basket',
            quantity_available=10,
            **kwargs
        )
    return _make


@pytest.fixture
def active_listing(make_listing):
    return make_listing()