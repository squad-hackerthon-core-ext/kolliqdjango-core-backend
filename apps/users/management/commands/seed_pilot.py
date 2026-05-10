"""
Seed pilot demo data for Kolliq.

Creates:
  - 8 marketplace categories
  - DemoFloat with ₦500,000
  - 12 test users across 4 score tiers (3 per tier)
  - Wallets, scores, savings pots, active loans, active insurance policies

Run once at deploy. Safe to re-run — uses get_or_create throughout.

Usage:
    python manage.py seed_pilot
    python manage.py seed_pilot --skip-if-exists   # silent no-op if data exists
    python manage.py seed_pilot --reset            # WARNING: clears all seed data first
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random

User = get_user_model()

SEED_PHONES = [
    '+2348011001001', '+2348011001002', '+2348011001003',
    '+2348011001004', '+2347022001001', '+2347022001002',
    '+2348011001005', '+2347022001003', '+2348011001006',
    '+2348011001007', '+2347022001004', '+2348011001008',
]

TIERS = [
    # (phone, name, role, score, wallet_balance, skills, city, area)
    ('+2348011001001', 'Tunde Adeyemi',   'worker',   15,  2500,   ['delivery'],              'Lagos', 'Surulere'),
    ('+2348011001002', 'Emeka Okafor',    'worker',   18,  1800,   ['construction'],          'Lagos', 'Apapa'),
    ('+2348011001003', 'Fatima Yusuf',    'worker',   12,   900,   ['cleaning'],              'Lagos', 'Ikeja'),
    ('+2348011001004', 'Chidi Nwosu',     'worker',   38,  8500,   ['delivery'],              'Lagos', 'Lekki'),
    ('+2347022001001', 'Amina Bello',     'trader',   45, 22000,   [],                        'Kano',  'Kano Central Market'),
    ('+2347022001002', 'Ngozi Obi',       'trader',   32, 15000,   [],                        'Lagos', 'Balogun Market'),
    ('+2348011001005', 'Seun Adesanya',   'worker',   62, 18000,   ['delivery', 'market'],    'Lagos', 'Surulere'),
    ('+2347022001003', 'Hauwa Musa',      'trader',   58, 35000,   [],                        'Abuja', 'Wuse Market'),
    ('+2348011001006', 'Biodun Faleke',   'worker',   68, 42000,   ['security'],              'Lagos', 'Victoria Island'),
    ('+2348011001007', 'Kelechi Eze',     'worker',   85, 67000,   ['delivery'],              'Lagos', 'Surulere'),
    ('+2347022001004', 'Zainab Sule',     'trader',   91, 88000,   [],                        'Kano',  'Sabon Gari Market'),
    ('+2348011001008', 'Rotimi Ade',      'worker',   78, 54000,   ['teaching'],              'Lagos', 'Yaba'),
]

LOCATION_MAP = {
    'Lagos':   ('6.5244', '3.3792'),
    'Kano':    ('12.0022', '8.5920'),
    'Abuja':   ('9.0579', '7.4951'),
}

CATEGORIES = [
    ('Food & Groceries',  'food-groceries',      '🍅'),
    ('Clothing & Fabric', 'clothing-fabric',      '👗'),
    ('Electronics',       'electronics',          '📱'),
    ('Household Goods',   'household-goods',      '🏠'),
    ('Farm Produce',      'farm-produce',         '🌽'),
    ('Building Materials','building-materials',   '🧱'),
    ('Services',          'services',             '🔧'),
    ('Other',             'other',                '📦'),
]


class Command(BaseCommand):
    help = 'Seed Kolliq pilot demo data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-if-exists',
            action='store_true',
            help='Exit silently if seed data already exists',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing seed users before re-seeding (DESTRUCTIVE)',
        )

    def handle(self, *args, **options):
        from apps.wallets.models import Wallet
        from apps.scoring.models import EconomicIdentityScore
        from apps.financial_services.models import (
            DemoFloat, SavingsPot, Loan, InsurancePolicy
        )
        from apps.marketplace.models import Category

        # ── Skip check ────────────────────────────────────────────
        if options['skip_if_exists']:
            if User.objects.filter(phone='+2348011001001').exists():
                self.stdout.write('Seed data exists — skipping.')
                return

        # ── Reset ─────────────────────────────────────────────────
        if options['reset']:
            self.stdout.write(self.style.WARNING('Resetting seed data...'))
            User.objects.filter(phone__in=SEED_PHONES).delete()
            DemoFloat.objects.filter(id=1).delete()
            self.stdout.write('  Seed users deleted.')

        self.stdout.write('🌱 Seeding Kolliq pilot data...\n')

        # ── Categories ────────────────────────────────────────────
        for name, slug, icon in CATEGORIES:
            _, created = Category.objects.get_or_create(
                slug=slug, defaults={'name': name, 'icon': icon}
            )
        self.stdout.write(f'  ✅ {len(CATEGORIES)} categories ready')

        # ── Demo Float ────────────────────────────────────────────
        demo_float, created = DemoFloat.objects.get_or_create(
            id=1, defaults={'balance': Decimal('500000')}
        )
        if not created and demo_float.balance < Decimal('100000'):
            demo_float.balance = Decimal('500000')
            demo_float.save()
        self.stdout.write(f'  ✅ DemoFloat: ₦{demo_float.balance:,.0f}')

        # ── Tiered users ──────────────────────────────────────────
        created_count = 0
        for phone, name, role, score, balance, skills, city, area in TIERS:
            lat, lng = LOCATION_MAP.get(city, ('6.5244', '3.3792'))

            user, user_created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    'full_name': name,
                    'role': role,
                    'location_city': city,
                    'location_area': area,
                    'location_lat': Decimal(lat),
                    'location_lng': Decimal(lng),
                    'skills': skills,
                    'onboarding_complete': True,
                    'trade_category': 'food' if role == 'trader' else '',
                    'market_name': area if role == 'trader' else '',
                }
            )
            if user_created:
                created_count += 1

            # Wallet
            Wallet.objects.update_or_create(
                user=user,
                defaults={
                    'balance': Decimal(str(balance)),
                    'squad_account_number': f'100{phone[-7:]}',
                    'squad_account_name': name,
                    'squad_bank_name': 'GTBank',
                    'squad_creation_status': 'created',
                }
            )

            # Score
            score_obj, _ = EconomicIdentityScore.objects.update_or_create(
                user=user,
                defaults={
                    'score': score,
                    'breakdown': {
                        'base': 10,
                        'gigs_completed': max(0, score - 20) if role == 'worker' else 0,
                        'transactions_recorded': max(0, score - 15) if role == 'trader' else 0,
                        'ratings_received': min(score // 10, 15),
                    },
                    'savings_unlocked': score >= 20,
                    'insurance_unlocked': score >= 70,
                    'loan_unlocked': score >= 50,
                }
            )

            # Savings pot (score >= 20)
            if score >= 20:
                SavingsPot.objects.get_or_create(
                    user=user,
                    defaults={
                        'balance': Decimal(str(int(balance * 0.08))),
                        'total_deposited': Decimal(str(int(balance * 0.08))),
                        'total_interest_earned': Decimal(str(int(balance * 0.002))),
                    }
                )

            # Active loan (score 50-74 — shows mid-repayment)
            if 50 <= score <= 74:
                if not user.loans.filter(
                    status__in=['active', 'partially_repaid']
                ).exists():
                    loan_amount = Decimal('10000') if score < 60 else Decimal('15000')
                    total_rep = (loan_amount * Decimal('1.05')).quantize(Decimal('0.01'))
                    weekly = (total_rep / 4).quantize(Decimal('0.01'))
                    Loan.objects.create(
                        user=user,
                        amount=loan_amount,
                        interest_rate_monthly=Decimal('5.00'),
                        total_repayable=total_rep,
                        amount_repaid=weekly,   # 1 installment paid
                        status='partially_repaid',
                        funding_source='demo_float',
                        repayment_schedule=[
                            {'week': 1, 'due_date': '2026-04-01', 'amount': str(weekly), 'paid': True, 'paid_at': '2026-04-01T08:00:00'},
                            {'week': 2, 'due_date': '2026-04-08', 'amount': str(weekly), 'paid': False},
                            {'week': 3, 'due_date': '2026-04-15', 'amount': str(weekly), 'paid': False},
                            {'week': 4, 'due_date': '2026-04-22', 'amount': str(weekly), 'paid': False},
                        ]
                    )

            # Active insurance (score >= 75)
            if score >= 75:
                if not user.insurance_policies.filter(status='active').exists():
                    days = random.randint(8, 25)
                    InsurancePolicy.objects.create(
                        user=user,
                        daily_premium=Decimal('200'),
                        coverage_limit=Decimal('50000'),
                        days_active=days,
                        total_premiums_paid=Decimal(str(days * 200)),
                        status='active',
                        funding_source='demo_float',
                    )

            action = 'created' if user_created else 'updated'
            self.stdout.write(
                f'  {"✨" if user_created else "✅"} {name:<20} '
                f'score={score:>3} wallet=₦{balance:>8,} [{action}]'
            )

        self.stdout.write(
            f'\n✅ Seeding complete: '
            f'{created_count} users created, '
            f'{len(TIERS) - created_count} already existed.'
        )
        self.stdout.write(
            '\n📋 Score tier summary:\n'
            '   Tier 1 (10–20): Tunde, Emeka, Fatima  → job matching only\n'
            '   Tier 2 (30–50): Chidi, Amina, Ngozi   → savings unlocked\n'
            '   Tier 3 (55–70): Seun, Hauwa, Biodun    → loans pre-qualified\n'
            '   Tier 4 (75–100): Kelechi, Zainab, Rotimi → insurance active\n'
        )