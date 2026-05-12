# apps/users/management/commands/seed_employers.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import time

User = get_user_model()

EMPLOYER_PHONES = [
    '+2348051003001', '+2348051003002', '+2348051003003',
    '+2347061003001', '+2347061003002', '+2347061003003',
]

# phone, full_name, role, score, balance, city, area, bvn, dob, business_name
EMPLOYERS = [
    ('+2348051003001', 'Kunle David Adebayo',     'employer', 44,  85000,  'Lagos', 'Victoria Island',  '22222222222', '05/10/1982', 'Adebayo Logistics Ltd'),
    ('+2348051003002', 'Priscilla Blessing Okafor',  'employer', 38,  62000,  'Lagos', 'Ikoyi',            '22222222222', '09/23/1986', 'Prisco Events & Catering'),
    ('+2348051003003', 'Babatunde Gold Lawal',   'employer', 55, 140000,  'Lagos', 'Lekki Phase 1',    '22222222222', '02/14/1979', 'Lawal Construction Works'),
    ('+2347061003001', 'Amaka Cecilia Okonkwo',     'employer', 41,  73000,  'Abuja', 'Maitama',          '22222222222', '11/30/1984', 'Amaka Cleaning Services'),
    ('+2347061003002', 'Suleiman Ismail Haruna',   'employer', 60, 210000,  'Abuja', 'Wuse II',          '22222222222', '07/08/1976', 'Haruna Properties'),
    ('+2347061003003', 'Ngozi Jessica Eze-Williams','employer', 47,  95000,  'Lagos', 'Surulere',         '22222222222', '04/19/1981', 'EzeWilliams Staffing'),
]

LOCATION_MAP = {
    'Lagos': ('6.5244', '3.3792'),
    'Abuja': ('9.0579', '7.4951'),
}


class Command(BaseCommand):
    help = 'Seed employer accounts separately from pilot workers/traders'

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

        if options['skip_if_exists']:
            if User.objects.filter(phone='+2348051003001').exists():
                self.stdout.write('Employer seed data exists — skipping.')
                return

        if options['reset']:
            self.stdout.write(self.style.WARNING('Resetting employer seed data...'))
            User.objects.filter(phone__in=EMPLOYER_PHONES).delete()

        # ── Squad connection ───────────────────────────────────────────
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

        self.stdout.write('🌱 Seeding employers...\n')

        for phone, name, role, score, balance, city, area, bvn, dob, business_name in EMPLOYERS:
            lat, lng = LOCATION_MAP.get(city, ('6.5244', '3.3792'))
            parts = name.strip().split()
            first_name = parts[0]
            middle_name = parts [1] if len(parts) >= 3 else ''
            last_name  = parts[1] if len(parts) >= 1 else parts[0]

            user, created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    'full_name':           name,
                    'role':                'employer',
                    'location_city':       city,
                    'location_area':       area,
                    'location_lat':        Decimal(lat),
                    'location_lng':        Decimal(lng),
                    'business_name':       business_name,
                    'skills':              [],
                    'onboarding_complete': True,
                }
            )

            if created:
                user.set_pin('1234')
                user.save(update_fields=['pin'])
                self.stdout.write(f'  👤 Created: {name} — {business_name}')
            else:
                self.stdout.write(f'  ⏭  Exists:  {name} — skipping user creation')

            # ── Squad VA ──────────────────────────────────────────────
            va_number = None
            va_status = 'pending'

            if use_squad and squad:
                from services.squad import SquadAPIError

                try:
                    existing = squad.get_customer_by_identifier(str(user.id))
                    va_number = existing.get('virtual_account_number', '')
                    self.stdout.write(f'  ↩  {name:<28} VA exists: {va_number}')
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
                            f'  ✨ {name:<28} VA: {va_number} (GTBank)'
                        ))
                        time.sleep(0.5)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f'  ⚠  {name:<28} VA failed: {e}'
                        ))
                        va_status = 'failed'

            # Fallback fake VA
            if not va_number:
                va_number = f'080{str(abs(hash(phone)))[:7]}'
                va_status = 'created' if not use_squad else 'failed'
                if not use_squad:
                    self.stdout.write(f'  🔧 {name:<28} fake VA: {va_number}')

            # Wallet
            Wallet.objects.update_or_create(
                user=user,
                defaults={
                    'balance':               Decimal(str(balance)),
                    'squad_account_number':  va_number,
                    'squad_account_name':    name,
                    'squad_bank_name':       'GTBank',
                    'squad_creation_status': va_status,
                }
            )

            # Score
            EconomicIdentityScore.objects.update_or_create(
                user=user,
                defaults={
                    'score': score,
                    'breakdown': {
                        'base':              10,
                        'jobs_posted':       max(0, score - 10),
                        'ratings_received':  min(score // 10, 15),
                    },
                    'savings_unlocked':   score >= 20,
                    'insurance_unlocked': score >= 70,
                    'loan_unlocked':      score >= 50,
                }
            )

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Done. {len(EMPLOYERS)} employers seeded.\n'
        ))
        self.stdout.write(
            '📋 Employers:\n'
            '  Kunle Adebayo      — Adebayo Logistics Ltd      (Lagos)\n'
            '  Priscilla Okafor   — Prisco Events & Catering   (Lagos)\n'
            '  Babatunde Lawal    — Lawal Construction Works    (Lagos)\n'
            '  Amaka Okonkwo      — Amaka Cleaning Services     (Abuja)\n'
            '  Suleiman Haruna    — Haruna Properties           (Abuja)\n'
            '  Ngozi Eze-Williams — EzeWilliams Staffing        (Lagos)\n'
            '\n🔑 Default PIN for all employers: 1234\n'
        )