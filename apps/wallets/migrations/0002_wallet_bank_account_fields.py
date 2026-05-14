# apps/wallets/migrations/XXXX_wallet_bank_account_fields.py
# Rename this file to the next migration number in your wallets app
# e.g. 0004_wallet_bank_account_fields.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # ── Replace with your actual last wallets migration ──────────────────
        ('wallets', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='bank_account_number',
            field=models.CharField(
                max_length=10,
                blank=True,
                default='',
                help_text='Worker\'s real bank account number for payouts',
            ),
        ),
        migrations.AddField(
            model_name='wallet',
            name='bank_code',
            field=models.CharField(
                max_length=10,
                blank=True,
                default='',
                help_text='Nigerian bank code (e.g. 058 for GTBank)',
            ),
        ),
        migrations.AddField(
            model_name='wallet',
            name='bank_name',
            field=models.CharField(
                max_length=100,
                blank=True,
                default='',
                help_text='Human-readable bank name',
            ),
        ),
        migrations.AddField(
            model_name='wallet',
            name='bank_account_name',
            field=models.CharField(
                max_length=150,
                blank=True,
                default='',
                help_text='Account name as returned by bank verification',
            ),
        ),
        migrations.AddField(
            model_name='wallet',
            name='bank_account_verified',
            field=models.BooleanField(
                default=False,
                help_text='True once account name has been verified via Squad/Paystack',
            ),
        ),
        migrations.AddField(
            model_name='wallet',
            name='bank_account_updated_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Last time bank details were saved',
            ),
        ),
    ]