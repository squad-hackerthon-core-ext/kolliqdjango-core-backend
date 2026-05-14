# apps/payments/management/commands/seed_demo_balances.py
"""
Demo Balance Seeder
====================
Does three things in one atomic operation:

  1. ESCROW MIGRATION  — Moves ₦100,000 from each employer's wallet
                         into their escrow_balance (simulates funded jobs).

  2. EMPLOYER FLOAT    — Tops up each employer's main wallet balance
                         by ₦500,000 so they can post more jobs in demos.

  3. DEMO FLOAT        — Credits the platform/arise wallet with ₦10,000,000
                         for demo liquidity.

Usage:
  python manage.py seed_demo_balances
  python manage.py seed_demo_balances --dry-run        # preview only, no DB writes
  python manage.py seed_demo_balances --reset          # zero out then re-apply
  python manage.py seed_demo_balances --escrow-only    # skip float & demo fund
  python manage.py seed_demo_balances --float-only     # skip escrow & demo fund
  python manage.py seed_demo_balances --demo-only      # skip escrow & employer float
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.contrib.auth import get_user_model

User = get_user_model()

# ── Config ────────────────────────────────────────────────────────────────────

EMPLOYER_PHONES = [
    '+2348051003001',  # Kunle Adebayo       — Adebayo Logistics Ltd
    '+2348051003002',  # Priscilla Okafor    — Prisco Events & Catering
    '+2348051003003',  # Babatunde Lawal     — Lawal Construction Works
    '+2347061003001',  # Amaka Okonkwo       — Amaka Cleaning Services
    '+2347061003002',  # Suleiman Haruna     — Haruna Properties
    '+2347061003003',  # Ngozi Eze-Williams  — EzeWilliams Staffing
]

ESCROW_MIGRATION_AMOUNT = Decimal('100000.00')   # debited from wallet → escrow_balance
EMPLOYER_FLOAT_AMOUNT   = Decimal('500000.00')   # credited directly to wallet balance
DEMO_FLOAT_AMOUNT       = Decimal('10000000.00') # credited to platform/arise wallet


class Command(BaseCommand):
    help = 'Seed demo balances: migrate escrow, float employer wallets, fund demo account'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Preview all changes without writing to the database'
        )
        parser.add_argument(
            '--reset', action='store_true',
            help='Zero out escrow_balance for all employers before re-applying'
        )
        parser.add_argument(
            '--escrow-only', action='store_true',
            help='Only run the escrow migration step'
        )
        parser.add_argument(
            '--float-only', action='store_true',
            help='Only run the employer wallet float step'
        )
        parser.add_argument(
            '--demo-only', action='store_true',
            help='Only fund the platform demo float wallet'
        )

    def handle(self, *args, **options):
        from apps.wallets.models import Wallet
        from apps.payments.models import Transaction
        from django.conf import settings

        dry_run     = options['dry_run']
        reset       = options['reset']
        escrow_only = options['escrow_only']
        float_only  = options['float_only']
        demo_only   = options['demo_only']

        # If none of the filter flags are set, run everything
        run_escrow = not (float_only or demo_only)
        run_float  = not (escrow_only or demo_only)
        run_demo   = not (escrow_only or float_only)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\n🔍 DRY RUN — no database changes will be made.\n'
            ))

        # ── Duplicate run guard ───────────────────────────────────────────────
        # --demo-only is always safe to re-run (just tops up the float)
        # --reset explicitly opts in to re-running
        if not reset and not dry_run and not demo_only:
            already_seeded = Transaction.objects.filter(
                metadata__seeded_by='seed_demo_balances'
            ).exists()

            if already_seeded:
                self.stdout.write(self.style.WARNING(
                    '\n⚠️  seed_demo_balances has already been run before.\n'
                    '   Transactions from a previous run were detected.\n\n'
                    '   To re-run safely, use:\n'
                    '     --reset      zeros escrow first, then re-applies\n'
                    '     --dry-run    preview what would happen\n'
                    '     --demo-only  just top up the demo float again (always safe)\n\n'
                    '   Aborting to prevent duplicate balances.\n'
                ))
                return

        self.stdout.write('═' * 60)
        self.stdout.write('  Kolliq Demo Balance Seeder')
        self.stdout.write('═' * 60 + '\n')

        # ── Fetch employers ───────────────────────────────────────────────────
        employers = list(
            User.objects.filter(phone__in=EMPLOYER_PHONES)
                        .select_related('wallet')
        )

        if not employers:
            self.stdout.write(self.style.ERROR(
                '❌  No employer accounts found. Run seed_employers first.'
            ))
            return

        employers_by_phone = {u.phone: u for u in employers}

        # ── STEP 1: ESCROW MIGRATION ──────────────────────────────────────────
        if run_escrow:
            self.stdout.write('\n📦 STEP 1 — Escrow Migration (₦100,000 per employer)\n')
            self.stdout.write('-' * 55)

            for phone in EMPLOYER_PHONES:
                employer = employers_by_phone.get(phone)
                if not employer:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠  {phone} not found — skipping')
                    )
                    continue

                wallet = getattr(employer, 'wallet', None)
                if not wallet:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠  {employer.full_name} has no wallet — skipping'
                        )
                    )
                    continue

                current_balance = wallet.balance
                current_escrow  = wallet.escrow_balance

                if reset and not dry_run:
                    wallet.escrow_balance = Decimal('0.00')
                    wallet.save(update_fields=['escrow_balance', 'updated_at'])
                    current_escrow = Decimal('0.00')

                # Check sufficient balance
                if current_balance < ESCROW_MIGRATION_AMOUNT:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠  {employer.full_name:<28} '
                            f'balance ₦{current_balance:,.0f} < ₦{ESCROW_MIGRATION_AMOUNT:,.0f} — skipping'
                        )
                    )
                    continue

                new_balance = current_balance - ESCROW_MIGRATION_AMOUNT
                new_escrow  = current_escrow  + ESCROW_MIGRATION_AMOUNT

                self.stdout.write(
                    f'  👤 {employer.full_name:<28} '
                    f'balance ₦{current_balance:>10,.0f} → ₦{new_balance:>10,.0f} | '
                    f'escrow ₦{current_escrow:>9,.0f} → ₦{new_escrow:>9,.0f}'
                )

                if not dry_run:
                    with db_transaction.atomic():
                        wallet.balance        = new_balance
                        wallet.escrow_balance = new_escrow
                        wallet.save(update_fields=['balance', 'escrow_balance', 'updated_at'])

                        Transaction.objects.create(
                            user=employer,
                            transaction_type=Transaction.Type.ESCROW_HOLD,
                            amount=ESCROW_MIGRATION_AMOUNT,
                            status=Transaction.Status.SUCCESS,
                            description='Demo seed: escrow migration from wallet balance',
                            metadata={
                                'seeded_by': 'seed_demo_balances',
                                'source':    'wallet_balance',
                                'target':    'escrow_balance',
                            }
                        )

            self.stdout.write(self.style.SUCCESS(
                f'\n  ✅ Escrow migration complete — ₦{ESCROW_MIGRATION_AMOUNT:,.0f} per employer.\n'
            ))

        # ── STEP 2: EMPLOYER WALLET FLOAT ────────────────────────────────────
        if run_float:
            self.stdout.write('\n💰 STEP 2 — Employer Wallet Float (₦500,000 per employer)\n')
            self.stdout.write('-' * 55)

            for phone in EMPLOYER_PHONES:
                employer = employers_by_phone.get(phone)
                if not employer:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠  {phone} not found — skipping')
                    )
                    continue

                wallet = getattr(employer, 'wallet', None)
                if not wallet:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠  {employer.full_name} has no wallet — skipping'
                        )
                    )
                    continue

                current_balance = wallet.balance
                new_balance     = current_balance + EMPLOYER_FLOAT_AMOUNT

                self.stdout.write(
                    f'  👤 {employer.full_name:<28} '
                    f'₦{current_balance:>10,.0f} → ₦{new_balance:>10,.0f} '
                    f'(+₦{EMPLOYER_FLOAT_AMOUNT:,.0f})'
                )

                if not dry_run:
                    with db_transaction.atomic():
                        wallet.balance = new_balance
                        wallet.save(update_fields=['balance', 'updated_at'])

                        Transaction.objects.create(
                            user=employer,
                            transaction_type=Transaction.Type.CREDIT,
                            amount=EMPLOYER_FLOAT_AMOUNT,
                            status=Transaction.Status.SUCCESS,
                            description='Demo seed: employer wallet float top-up',
                            metadata={
                                'seeded_by': 'seed_demo_balances',
                                'source':    'demo_float',
                            }
                        )

            self.stdout.write(self.style.SUCCESS(
                f'\n  ✅ Employer float complete — ₦{EMPLOYER_FLOAT_AMOUNT:,.0f} added to each wallet.\n'
            ))

        # ── STEP 3: PLATFORM DEMO FLOAT ──────────────────────────────────────
        if run_demo:
            from apps.financial_services.models import DemoFloat

            self.stdout.write('\n🏦 STEP 3 — Platform Demo Float (₦10,000,000)\n')
            self.stdout.write('-' * 55)

            try:
                # DemoFloat always uses id=1 — consistent with seed_pilot.py
                demo_float, created = DemoFloat.objects.get_or_create(
                    id=1,
                    defaults={'balance': Decimal('0')}
                )

                current_balance = demo_float.balance
                new_balance     = current_balance + DEMO_FLOAT_AMOUNT

                self.stdout.write(
                    f'  🏦 DemoFloat (id=1) — {"created" if created else "existing"}\n'
                    f'     Current  : ₦{current_balance:>15,.0f}\n'
                    f'     Adding   : ₦{DEMO_FLOAT_AMOUNT:>15,.0f}\n'
                    f'     New Bal  : ₦{new_balance:>15,.0f}'
                )

                if not dry_run:
                    with db_transaction.atomic():
                        demo_float.balance = new_balance
                        demo_float.save(update_fields=['balance'])

                self.stdout.write(self.style.SUCCESS(
                    f'\n  ✅ Demo float complete — ₦{DEMO_FLOAT_AMOUNT:,.0f} credited.\n'
                ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  ❌  DemoFloat update failed: {e}'
                ))

        # ── SUMMARY ───────────────────────────────────────────────────────────
        self.stdout.write('═' * 60)
        self.stdout.write(self.style.SUCCESS('  ✅  seed_demo_balances complete!'))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                '  🔍  DRY RUN — rerun without --dry-run to apply changes.'
            ))
        self.stdout.write('═' * 60 + '\n')

        if not dry_run:
            self.stdout.write(
                '📊 Summary:\n'
                f'  Employers processed   : {len(employers)}\n'
                f'  Escrow per employer   : ₦{ESCROW_MIGRATION_AMOUNT:,.0f}\n'
                f'  Float per employer    : ₦{EMPLOYER_FLOAT_AMOUNT:,.0f}\n'
                f'  Platform demo float   : ₦{DEMO_FLOAT_AMOUNT:,.0f}\n'
                f'\n'
                f'  Total escrow moved    : ₦{ESCROW_MIGRATION_AMOUNT * len(employers):,.0f}\n'
                f'  Total float added     : ₦{EMPLOYER_FLOAT_AMOUNT * len(employers):,.0f}\n'
            )