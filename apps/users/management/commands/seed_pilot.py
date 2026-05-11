# apps/users/management/commands/seed_pilot.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random, time

User = get_user_model()

SEED_PHONES = [
    '+2348011001001', '+2348011001002', '+2348011001003',
    '+2348011001004', '+2347022001001', '+2347022001002',
    '+2348011001005', '+2347022001003', '+2348011001006',
    '+2348011001007', '+2347022001004', '+2348011001008',
]

TIERS = [
    ('+2348011001001', 'Tunde Adeyemi',  'worker',  15,  2500,  ['delivery'],           'Lagos', 'Surulere',          '22345678901', '04/15/1995'),
    ('+2348011001002', 'Emeka Okafor',   'worker',  18,  1800,  ['construction'],       'Lagos', 'Apapa',             '22345678902', '09/22/1990'),
    ('+2348011001003', 'Fatima Yusuf',   'worker',  12,   900,  ['cleaning'],           'Lagos', 'Ikeja',             '22345678903', '11/30/1998'),
    ('+2348011001004', 'Chidi Nwosu',    'worker',  38,  8500,  ['delivery'],           'Lagos', 'Lekki',             '22345678904', '07/18/1985'),
    ('+2347022001001', 'Amina Bello',    'trader',  45, 22000,  [],                     'Kano',  'Kano Central Market', '22345678905', '11/12/1978'),
    ('+2347022001002', 'Ngozi Obi',      'trader',  32, 15000,  [],                     'Lagos', 'Balogun Market',    '22345678906', '03/05/1988'),
    ('+2348011001005', 'Seun Adesanya',  'worker',  62, 18000,  ['delivery', 'market'], 'Lagos', 'Surulere',          '22345678907', '08/30/1961'),
    ('+2347022001003', 'Hauwa Musa',     'trader',  58, 35000,  [],                     'Abuja', 'Wuse Market',       '22345678908', '05/20/1980'),
    ('+2348011001006', 'Biodun Faleke',  'worker',  68, 42000,  ['security'],           'Lagos', 'Victoria Island',   '22345678909', '10/23/1955'),
    ('+2348011001007', 'Kelechi Eze',    'worker',  85, 67000,  ['delivery'],           'Lagos', 'Surulere',          '22345678910', '02/28/1938'),
    ('+2347022001004', 'Zainab Sule',    'trader',  91, 88000,  [],                     'Kano',  'Sabon Gari Market', '22345678911', '07/14/1932'),
    ('+2348011001008', 'Rotimi Ade',     'worker',  78, 54000,  ['teaching'],           'Lagos', 'Yaba',              '22345678912', '10/31/1945'),
]

LOCATION_MAP = {
    'Lagos': ('6.5244', '3.3792'),
    'Kano':  ('12.0022', '8.5920'),
    'Abuja': ('9.0579', '7.4951'),
}

CATEGORIES = [
    ('Food & Groceries',   'food-groceries',    '🍅'),
    ('Clothing & Fabric',  'clothing-fabric',   '👗'),
    ('Electronics',        'electronics',       '📱'),
    ('Household Goods',    'household-goods',   '🏠'),
    ('Farm Produce',       'farm-produce',      '🌽'),
    ('Building Materials', 'building-materials','🧱'),
    ('Services',           'services',          '🔧'),
    ('Other',              'other',             '📦'),
]


class Command(BaseCommand):
    help = 'Seed pilot data — each user gets a real Squad sandbox VA'

    def add_arguments(self, parser):
        parser.add_argument('--skip-if-exists', action='store_true')
        parser.add_argument('--reset', action='store_true')
        parser.add_argument(
            '--no-squad', action='store_true',
            help='Skip Squad VA creation, use fake numbers (for offline dev)'
        )

    def handle(self, *args, **options):
        from apps.wallets.models import Wallet
        from apps.scoring.models import EconomicIdentityScore
        from apps.financial_services.models import (
            DemoFloat, SavingsPot, Loan, InsurancePolicy
        )
        from apps.marketplace.models import Category

        if options['skip_if_exists']:
            if User.objects.filter(phone='+2348011001001').exists():
                self.stdout.write('Seed data exists — skipping.')
                return

        if options['reset']:
            self.stdout.write(self.style.WARNING('Resetting seed data...'))
            User.objects.filter(phone__in=SEED_PHONES).delete()
            DemoFloat.objects.filter(id=1).delete()

        # ── Try connect to Squad ───────────────────────────────────
        use_squad = not options['no_squad']
        squad = None
        if use_squad:
            try:
                from services.squad import SquadService
                squad = SquadService()
                self.stdout.write('✅ Squad connected — creating real sandbox VAs\n')
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'Squad unavailable ({e}) — using fake VA numbers.\n'
                ))
                use_squad = False

        self.stdout.write('🌱 Seeding...\n')

        # Categories
        for name, slug, icon in CATEGORIES:
            Category.objects.get_or_create(
                slug=slug, defaults={'name': name, 'icon': icon}
            )
        self.stdout.write(f'  ✅ {len(CATEGORIES)} categories')

        # DemoFloat
        DemoFloat.objects.update_or_create(
            id=1, defaults={'balance': Decimal('500000')}
        )
        self.stdout.write('  ✅ DemoFloat ₦500,000')

        self.stdout.write('\n  Creating users + VAs...\n')

        for phone, name, role, score, balance, skills, city, area, bvn, dob in TIERS:
            lat, lng = LOCATION_MAP.get(city, ('6.5244', '3.3792'))
            parts = name.strip().split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else parts[0]

            user, created = User.objects.get_or_create(
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
            
            # Set default pin if user was created
            if created:
                user.set_pin('1233')
                user.save(update_fields=['pin'])

            # ── Squad VA ──────────────────────────────────────────
            va_number = None
            va_status = 'pending'

            if use_squad and squad:
                from services.squad import SquadAPIError
                # Check existing first
                try:
                    existing = squad.get_customer_by_identifier(str(user.id))
                    va_number = existing.get('virtual_account_number', '')
                    self.stdout.write(f'  ↩  {name:<22} VA exists: {va_number}')
                    va_status = 'created'
                except Exception:
                    pass

                if not va_number:
                    try:
                        phone_clean = phone.replace('+234', '0')
                        result = squad.create_virtual_account(
                            customer_identifier=str(user.id),
                            first_name=first_name,
                            middle_name='middle_name',
                            last_name=last_name,
                            phone=phone_clean,
                            email=f'{str(user.id)[:8]}@kolliq.app',
                            bvn=bvn,
                            dob=dob,
                            gender='1',
                            address=area,
                        )
                        va_number = result['virtual_account_number']
                        va_status = 'created'
                        self.stdout.write(self.style.SUCCESS(
                            f'  ✨ {name:<22} VA: {va_number} (GTBank)'
                        ))
                        time.sleep(0.5)  # avoid rate limiting
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f'  ⚠  {name:<22} VA failed: {e}'
                        ))
                        va_status = 'failed'

            # Fallback fake VA number — deterministic per phone
            if not va_number:
                va_number = f'070{str(abs(hash(phone)))[:7]}'
                va_status = 'created' if not use_squad else 'failed'
                if not use_squad:
                    self.stdout.write(
                        f'  🔧 {name:<22} fake VA: {va_number}'
                    )

            # Wallet
            Wallet.objects.update_or_create(
                user=user,
                defaults={
                    'balance': Decimal(str(balance)),
                    'squad_account_number': va_number,
                    'squad_account_name': name,
                    'squad_bank_name': 'GTBank',
                    'squad_creation_status': va_status,
                }
            )

            # Score
            EconomicIdentityScore.objects.update_or_create(
                user=user,
                defaults={
                    'score': score,
                    'breakdown': {
                        'base': 10,
                        'gigs_completed': max(0, (score-10)//2) if role == 'worker' else 0,
                        'transactions_recorded': max(0, score-20) if role == 'trader' else 0,
                        'ratings_received': min(score//10, 15),
                    },
                    'savings_unlocked': score >= 20,
                    'insurance_unlocked': score >= 70,
                    'loan_unlocked': score >= 50,
                }
            )

            # Savings pot
            if score >= 20:
                SavingsPot.objects.get_or_create(
                    user=user,
                    defaults={
                        'balance': Decimal(str(int(balance * 0.08))),
                        'total_deposited': Decimal(str(int(balance * 0.08))),
                        'total_interest_earned': Decimal(str(int(balance * 0.002))),
                    }
                )

            # Loan in progress
            if 50 <= score <= 74:
                if not user.loans.filter(status__in=['active', 'partially_repaid']).exists():
                    amt = Decimal('10000') if score < 60 else Decimal('15000')
                    total = (amt * Decimal('1.05')).quantize(Decimal('0.01'))
                    weekly = (total / 4).quantize(Decimal('0.01'))
                    Loan.objects.create(
                        user=user, amount=amt,
                        interest_rate_monthly=Decimal('5.00'),
                        total_repayable=total, amount_repaid=weekly,
                        status='partially_repaid', funding_source='demo_float',
                        repayment_schedule=[
                            {'week': 1, 'due_date': '2026-04-01', 'amount': str(weekly), 'paid': True},
                            {'week': 2, 'due_date': '2026-04-08', 'amount': str(weekly), 'paid': False},
                            {'week': 3, 'due_date': '2026-04-15', 'amount': str(weekly), 'paid': False},
                            {'week': 4, 'due_date': '2026-04-22', 'amount': str(weekly), 'paid': False},
                        ]
                    )

            # Active insurance
            if score >= 75:
                if not user.insurance_policies.filter(status='active').exists():
                    days = random.randint(8, 25)
                    InsurancePolicy.objects.create(
                        user=user, daily_premium=Decimal('200'),
                        coverage_limit=Decimal('50000'), days_active=days,
                        total_premiums_paid=Decimal(str(days * 200)),
                        status='active', funding_source='demo_float',
                    )

        # Simulate demo payments if Squad is connected
        if use_squad and squad:
            self._simulate_payments(squad)

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Done. {len(TIERS)} users seeded.\n'
        ))
        self.stdout.write(
            '📋 Tiers: Tunde/Emeka/Fatima (10-20) | Chidi/Amina/Ngozi (30-50) | '
            'Seun/Hauwa/Biodun (55-70) | Kelechi/Zainab/Rotimi (75-100)\n'
            '\n🧪 Test payment: python manage.py simulate_payment --va <VA> --amount 3500\n'
        )

    def _simulate_payments(self, squad):
        from django.conf import settings
        from services.squad import SquadAPIError

        self.stdout.write('\n  Simulating demo payments...\n')
        escrow_va = getattr(settings, 'KOLLIQ_ESCROW_VIRTUAL_ACCOUNT', '')

        if not escrow_va:
            self.stdout.write(self.style.WARNING(
                '  ⚠  No escrow VA set. Run: python manage.py create_system_accounts'
            ))
            return

        # ₦3,500 to escrow for a demo job
        try:
            squad.simulate_payment(escrow_va, Decimal('3500'))
            self.stdout.write(self.style.SUCCESS(
                f'  ✅ ₦3,500 → escrow VA {escrow_va}'
            ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠  Escrow sim failed: {e}'))

        # ₦2,000 to Amina's personal VA
        amina = User.objects.filter(phone='+2347022001001').first()
        if amina:
            try:
                amina_va = amina.wallet.squad_account_number
                if amina_va and amina.wallet.squad_creation_status == 'created':
                    squad.simulate_payment(amina_va, Decimal('2000'))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✅ ₦2,000 → Amina VA {amina_va}'
                    ))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠  Amina sim failed: {e}'))