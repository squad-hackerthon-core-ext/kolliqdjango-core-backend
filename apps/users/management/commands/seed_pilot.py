# apps/users/management/commands/seed_pilot.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random, time

User = get_user_model()

SEED_PHONES = [
    '+2348031002001', '+2348031002002', '+2348031002003', '+2348031002004',
    '+2348031002005', '+2347041002001', '+2347041002002', '+2348031002006',
    '+2347041002003', '+2348031002007', '+2348031002008', '+2347041002004',
    '+2348031002009', '+2348031002010', '+2347041002005', '+2348031002011',
    '+2347041002006', '+2348031002012', '+2348031002013', '+2347041002007',
]

# phone, full_name, role, score, balance, skills, city, area, bvn, dob
TIERS = [
    # ── Tier 1: Score 10–20 (new / low activity) ─────────────────────────
    ('+2348031002001', 'Adaeze James Okonkwo',   'worker',  11,  1200,  ['cleaning'],              'Lagos', 'Ojodu',              '22222222222', '06/14/2000'),
    ('+2348031002002', 'Musa Moshood Garba',        'worker',  14,  2100,  ['delivery'],              'Kano',  'Fagge',              '22222222222', '03/28/1997'),
    ('+2348031002003', 'Chisom Stella Eze',        'worker',  17,  1750,  ['laundry'],               'Lagos', 'Mushin',             '22222222222', '09/05/1999'),
    ('+2348031002004', 'Yetunde Victoria Badmus',    'worker',  19,  3000,  ['cooking'],               'Lagos', 'Agege',              '22222222222', '12/11/1996'),

    # ── Tier 2: Score 25–45 (growing, unlocked savings) ──────────────────
    ('+2348031002005', 'Ifeanyi Max Obiora',    'worker',  27,  6500,  ['delivery', 'errands'],   'Lagos', 'Mainland',           '22222222222', '07/22/1993'),
    ('+2347041002001', 'Raliat Adeleke Suleiman',   'trader',  31, 12000,  [],                        'Abuja', 'Garki Market',       '22222222222', '02/17/1989'),
    ('+2347041002002', 'Uche Stephen Nnamdi',       'worker',  35,  9800,  ['carpentry'],             'Lagos', 'Ikorodu',            '22222222222', '11/04/1991'),
    ('+2348031002006', 'Blessing Adetola Ajayi',    'trader',  42, 18500,  [],                        'Lagos', 'Tejuosho Market',    '22222222222', '05/30/1987'),

    # ── Tier 3: Score 50–70 (loan eligible, active) ───────────────────────
    ('+2347041002003', 'Abdullahi Maliq Danjuma', 'trader',  52, 27000,  [],                        'Kano',  'Singer Market',      '22222222222', '08/09/1983'),
    ('+2348031002007', 'Ngozi Esther Anyanwu',     'worker',  55, 21000,  ['teaching', 'tutoring'],  'Lagos', 'Gbagada',            '22222222222', '04/16/1986'),
    ('+2348031002008', 'Taiwo David Olawale',     'worker',  61, 24500,  ['delivery', 'market'],    'Lagos', 'Ikotun',             '22222222222', '01/25/1984'),
    ('+2347041002004', 'Hadiza Halimat Abubakar',   'trader',  67, 41000,  [],                        'Abuja', 'Nyanya Market',      '22222222222', '10/03/1980'),
    ('+2348031002009', 'Emeka Joshua Nwosu',       'worker',  69, 33000,  ['plumbing'],              'Lagos', 'Festac',             '22222222222', '06/18/1979'),

    # ── Tier 4: Score 75–100 (insurance eligible, top earners) ───────────
    ('+2348031002010', 'Funmilayo Aderonke Adebisi', 'trader',  76, 58000,  [],                        'Lagos', 'Alaba Market',       '22222222222', '09/27/1975'),
    ('+2347041002005', 'Ibrahim Ola Lawal',     'worker',  79, 49000,  ['security', 'driving'],   'Lagos', 'Ajah',               '22222222222', '03/12/1972'),
    ('+2348031002011', 'Nneka Chioma Obi',         'trader',  83, 72000,  [],                        'Enugu', 'Ogbete Market',      '22222222222', '11/08/1969'),
    ('+2347041002006', 'Salihu Isa Balarabe',   'trader',  88, 95000,  [],                        'Kano',  'Kurmi Market',       '22222222222', '07/31/1965'),
    ('+2348031002012', 'Olumide Joshua Adeyinka',  'worker',  91, 81000,  ['electrical'],            'Lagos', 'Ojota',              '22222222222', '05/14/1960'),
    ('+2348031002013', 'Aisha Precious Mahmud',      'trader',  95, 110000, [],                        'Abuja', 'Wuse II Market',     '22222222222', '02/20/1957'),
    ('+2347041002007', 'Chukwuemeka David Osei',  'worker',  98, 134000, ['construction', 'tiling'],'Lagos', 'Lekki Phase 1',      '22222222222', '08/03/1953'),
]

LOCATION_MAP = {
    'Lagos': ('6.5244', '3.3792'),
    'Kano':  ('12.0022', '8.5920'),
    'Abuja': ('9.0579', '7.4951'),
    'Enugu': ('6.4584', '7.5464'),
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
    help = 'Seed pilot data — 20 users across 4 score tiers with real Squad sandbox VAs'

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
            if User.objects.filter(phone='+2348031002001').exists():
                self.stdout.write('Seed data exists — skipping.')
                return

        if options['reset']:
            self.stdout.write(self.style.WARNING('Resetting seed data...'))
            User.objects.filter(phone__in=SEED_PHONES).delete()
            DemoFloat.objects.filter(id=1).delete()

        # ── Squad connection ───────────────────────────────────────────────
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
            id=1, defaults={'balance': Decimal('1000000')}
        )
        self.stdout.write('  ✅ DemoFloat ₦1,000,000')

        self.stdout.write('\n  Creating users + VAs...\n')

        for phone, name, role, score, balance, skills, city, area, bvn, dob in TIERS:
            lat, lng = LOCATION_MAP.get(city, ('6.5244', '3.3792'))
            parts = name.strip().split()
            first_name  = parts[0]
            middle_name = parts[1] if len(parts) >= 3 else ''
            last_name   = parts[-1] if len(parts) >= 2 else parts[0]
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

            if created:
                user.set_pin('1234')
                user.save(update_fields=['pin'])

            # ── Squad VA ──────────────────────────────────────────────────
            va_number = None
            va_status = 'pending'

            if use_squad and squad:
                from services.squad import SquadAPIError

                try:
                    existing = squad.get_customer_by_identifier(str(user.id))
                    va_number = existing.get('virtual_account_number', '')
                    self.stdout.write(f'  ↩  {name:<26} VA exists: {va_number}')
                    va_status = 'created'
                except Exception:
                    pass

                if not va_number:
                    try:
                        phone_clean = phone.replace('+234', '0')
                        result = squad.create_virtual_account(
                            customer_identifier=str(user.id),
                            first_name=first_name,
                            middle_name=middle_name,
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
                            f'  ✨ {name:<26} VA: {va_number} (GTBank)'
                        ))
                        time.sleep(0.5)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f'  ⚠  {name:<26} VA failed: {e}'
                        ))
                        va_status = 'failed'

            # Fallback fake VA
            if not va_number:
                va_number = f'070{str(abs(hash(phone)))[:7]}'
                va_status = 'created' if not use_squad else 'failed'
                if not use_squad:
                    self.stdout.write(f'  🔧 {name:<26} fake VA: {va_number}')

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
                        'gigs_completed': max(0, (score - 10) // 2) if role == 'worker' else 0,
                        'transactions_recorded': max(0, score - 20) if role == 'trader' else 0,
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

            # Loan in progress (score 50–74)
            if 50 <= score <= 74:
                if not user.loans.filter(status__in=['active', 'partially_repaid']).exists():
                    amt = Decimal('12000') if score < 60 else Decimal('20000')
                    total = (amt * Decimal('1.05')).quantize(Decimal('0.01'))
                    weekly = (total / 4).quantize(Decimal('0.01'))
                    Loan.objects.create(
                        user=user, amount=amt,
                        interest_rate_monthly=Decimal('5.00'),
                        total_repayable=total, amount_repaid=weekly,
                        status='partially_repaid', funding_source='demo_float',
                        repayment_schedule=[
                            {'week': 1, 'due_date': '2026-05-01', 'amount': str(weekly), 'paid': True},
                            {'week': 2, 'due_date': '2026-05-08', 'amount': str(weekly), 'paid': False},
                            {'week': 3, 'due_date': '2026-05-15', 'amount': str(weekly), 'paid': False},
                            {'week': 4, 'due_date': '2026-05-22', 'amount': str(weekly), 'paid': False},
                        ]
                    )

            # Active insurance (score >= 75)
            if score >= 75:
                if not user.insurance_policies.filter(status='active').exists():
                    days = random.randint(10, 28)
                    InsurancePolicy.objects.create(
                        user=user, daily_premium=Decimal('200'),
                        coverage_limit=Decimal('50000'), days_active=days,
                        total_premiums_paid=Decimal(str(days * 200)),
                        status='active', funding_source='demo_float',
                    )

        if use_squad and squad:
            self._simulate_payments(squad)

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Done. {len(TIERS)} users seeded.\n'
        ))
        self.stdout.write(
            '📋 Tiers:\n'
            '  Score 10–20 : Adaeze, Musa, Chisom, Yetunde\n'
            '  Score 25–45 : Ifeanyi, Raliat, Uche, Blessing\n'
            '  Score 50–70 : Abdullahi, Ngozi, Taiwo, Hadiza, Emeka\n'
            '  Score 75–100: Funmilayo, Ibrahim, Nneka, Salihu, Olumide, Aisha, Chukwuemeka\n'
            '\n🔑 Default PIN for all users: 1234\n'
            '\n🧪 Test payment: python manage.py simulate_payment --va <VA> --amount 5000\n'
        )

    def _simulate_payments(self, squad):
        from django.conf import settings

        self.stdout.write('\n  Simulating demo payments...\n')
        escrow_va = getattr(settings, 'KOLLIQ_ESCROW_VIRTUAL_ACCOUNT', '')

        if not escrow_va:
            self.stdout.write(self.style.WARNING(
                '  ⚠  No escrow VA set. Run: python manage.py create_system_accounts'
            ))
            return

        # ₦5,000 to escrow for a demo job
        try:
            squad.simulate_payment(escrow_va, Decimal('5000'))
            self.stdout.write(self.style.SUCCESS(
                f'  ✅ ₦5,000 → escrow VA {escrow_va}'
            ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠  Escrow sim failed: {e}'))

        # ₦3,000 to Raliat's personal VA (top trader in tier 2)
        raliat = User.objects.filter(phone='+2347041002001').first()
        if raliat:
            try:
                raliat_va = raliat.wallet.squad_account_number
                if raliat_va and raliat.wallet.squad_creation_status == 'created':
                    squad.simulate_payment(raliat_va, Decimal('3000'))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✅ ₦3,000 → Raliat VA {raliat_va}'
                    ))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠  Raliat sim failed: {e}'))