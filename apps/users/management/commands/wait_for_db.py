"""
Management command used in Docker entrypoint to wait for the
database to be ready before running migrations or starting the server.

Without this, Django crashes on startup if Postgres isn't ready yet.

Usage:
    python manage.py wait_for_db
    python manage.py wait_for_db --timeout 60
"""
import time
import sys
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Wait for database to be available before proceeding'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=60,
            help='Maximum seconds to wait (default: 60)',
        )
        parser.add_argument(
            '--interval',
            type=float,
            default=2.0,
            help='Seconds between retries (default: 2)',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        interval = options['interval']
        elapsed = 0

        self.stdout.write('Waiting for database...')

        while elapsed < timeout:
            try:
                conn = connections['default']
                conn.ensure_connection()
                self.stdout.write(
                    self.style.SUCCESS(f'Database ready after {elapsed:.0f}s')
                )
                return
            except OperationalError:
                self.stdout.write(
                    f'  Database unavailable — retrying in {interval}s '
                    f'({elapsed:.0f}s/{timeout}s elapsed)'
                )
                time.sleep(interval)
                elapsed += interval

        self.stdout.write(
            self.style.ERROR(
                f'Database not available after {timeout}s. Giving up.'
            )
        )
        sys.exit(1)