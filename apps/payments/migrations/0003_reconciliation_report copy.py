# apps/payments/migrations/XXXX_reconciliation_report.py
# Rename to next migration number e.g. 0005_reconciliation_report.py

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        # Replace with your actual last payments migration
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReconciliationReport',
            fields=[
                ('id',               models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('status',           models.CharField(max_length=20, choices=[('ok','OK'),('critical','Critical — Drift Detected'),('error','Error — Could Not Complete')])),
                ('expected_balance', models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)),
                ('actual_balance',   models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)),
                ('drift',            models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)),
                ('drift_percent',    models.DecimalField(max_digits=7,  decimal_places=4, null=True, blank=True)),
                ('breakdown',        models.JSONField(default=dict, blank=True)),
                ('error_message',    models.TextField(blank=True, default='')),
                ('ran_at',           models.DateTimeField()),
                ('completed_at',     models.DateTimeField(null=True, blank=True)),
                ('created_at',       models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-ran_at'],
                'verbose_name': 'Reconciliation Report',
                'verbose_name_plural': 'Reconciliation Reports',
            },
        ),
    ]