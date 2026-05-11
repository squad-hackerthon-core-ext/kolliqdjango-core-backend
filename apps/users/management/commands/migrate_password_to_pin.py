# apps/users/management/commands/migrate_password_to_pin.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

User = get_user_model()

SEED_PHONES = [
    '+2348011001001', '+2348011001002', '+2348011001003',
    '+2348011001004', '+2347022001001', '+2347022001002',
    '+2348011001005', '+2347022001003', '+2348011001006',
    '+2348011001007', '+2347022001004', '+2348011001008',
]

DEFAULT_PASSWORD = 'TestKolliq2026!'
DEFAULT_PIN      = '1233'  # What their PIN will be after migration — change if you prefer


class Command(BaseCommand):
    help = 'Migrate seeded users from password auth to PIN auth'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pin',
            type=str,
            default=DEFAULT_PIN,
            help=f'PIN to assign to migrated users (default: {DEFAULT_PIN})'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would happen without making any changes'
        )

    def handle(self, *args, **options):
        new_pin = options['pin']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('--- DRY RUN — no changes will be saved ---\n'))

        if not new_pin.isdigit() or not (4 <= len(new_pin) <= 6):
            self.stdout.write(self.style.ERROR('PIN must be 4-6 digits only.'))
            return

        migrated  = 0
        skipped   = 0
        not_found = 0
        bad_pass  = 0

        for phone in SEED_PHONES:
            try:
                user = User.objects.get(phone=phone)

                # Already has a PIN — nothing to do
                if user.pin:
                    self.stdout.write(f'  ⏭  {phone} ({user.full_name}) — already has PIN, skipping')
                    skipped += 1
                    continue

                # Verify the stored password really is the known default
                # before we touch anything — safety check
                if not check_password(DEFAULT_PASSWORD, user.password):
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠  {phone} ({user.full_name}) — password does not match default, skipping'
                    ))
                    bad_pass += 1
                    continue

                if not dry_run:
                    user.set_pin(new_pin)
                    user.save(update_fields=['pin'])

                migrated += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  ✅ {phone} ({user.full_name}) — {"would be " if dry_run else ""}migrated → PIN {new_pin}'
                ))

            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'  ⚠  {phone} — not found in DB'))
                not_found += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n{"[DRY RUN] " if dry_run else ""}Done.\n'
            f'  Migrated : {migrated}\n'
            f'  Skipped  : {skipped} (already had PIN)\n'
            f'  Bad pass : {bad_pass} (password did not match default)\n'
            f'  Not found: {not_found}\n'
        ))

        if not dry_run and migrated:
            self.stdout.write(
                f'All migrated users can now log in with PIN: {new_pin}\n'
                'Remind them to reset their PIN after first login.\n'
            )