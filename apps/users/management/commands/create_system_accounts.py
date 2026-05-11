"""
Run once to create Kolliq's two system virtual accounts on Squad:
  1. Kolliq Escrow    — employers pay here when posting jobs
  2. Kolliq Platform  — platform fees collect here

After running, copy the printed account numbers into .env:
  KOLLIQ_ESCROW_VIRTUAL_ACCOUNT=...
  KOLLIQ_PLATFORM_VIRTUAL_ACCOUNT=...
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Create Kolliq system virtual accounts on Squad (run once)'

    def handle(self, *args, **kwargs):
        from services.squad import SquadService, SquadAPIError

        squad = SquadService()

        accounts_to_create = [
            {
                'customer_identifier': settings.KOLLIQ_ESCROW_CUSTOMER_ID,
                'first_name': 'Kolliq',
                'last_name': 'Escrow',
                'middle_name': 'xpsiders',
                'phone': '08000000001',
                'email': 'escrow@kolliq.app',
                'label': 'ESCROW',
                'dob': '10/01/2000',   # Required by Squad but not actually used for VAs
                'env_key': 'KOLLIQ_ESCROW_VIRTUAL_ACCOUNT',
                'address': '123 Escrow St, Lagos',   # Required by Squad for virtual accounts
                'gender': '1',   # Required by Squad for virtual accounts
                'beneficiary_account': settings.SQUAD_BENEFICIARY_ACCOUNT,   # Required by Squad for settlement
                'bvn': '22222222222',   # Dummy BVN to satisfy Squad's validation (not actually used for VAs)
            },
            {
                'customer_identifier': settings.KOLLIQ_PLATFORM_CUSTOMER_ID,
                'first_name': 'Kolliq',
                'last_name': 'Platform',
                'middle_name': 'JMX',
                'phone': '08000000002',
                'email': 'platform@kolliq.app',
                'label': 'PLATFORM',
                'dob': '10/05/2000',   # Required by Squad but not actually used for VAs
                'env_key': 'KOLLIQ_PLATFORM_VIRTUAL_ACCOUNT',
                'address': '456 Platform Ave, Lagos',   # Required by Squad for virtual accounts
                'gender': '1',   # Required by Squad for virtual accounts
                'beneficiary_account': settings.SQUAD_BENEFICIARY_ACCOUNT,   # Required by Squad for settlement
                'bvn': '22222222222',   # Dummy BVN to satisfy Squad's validation (not actually used for VAs)
            },
        ]

        self.stdout.write('\nCreating Kolliq system virtual accounts on Squad...\n')

        for account in accounts_to_create:
            label = account.pop('label')
            env_key = account.pop('env_key')

            # Check if already exists first
            try:
                existing = squad.get_customer_by_identifier(
                    account['customer_identifier']
                )
                va_number = existing.get('virtual_account_number', '')
                self.stdout.write(
                    self.style.WARNING(
                        f"  [{label}] Already exists: {va_number}\n"
                        f"  Add to .env: {env_key}={va_number}\n"
                    )
                )
                continue
            except SquadAPIError:
                pass   # Doesn't exist yet, create it

            try:
                result = squad.create_virtual_account(**account)
                va_number = result['virtual_account_number']
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [{label}] Created: {va_number} (GTBank)\n"
                        f"  Add to .env: {env_key}={va_number}\n"
                    )
                )
            except SquadAPIError as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  [{label}] Failed: {e}\n"
                        f"  Raw: {e.raw}\n"
                    )
                )

        self.stdout.write(
            '\nDone. Copy the account numbers above into your .env file.\n'
            'Then restart Django for them to take effect.\n'
        )