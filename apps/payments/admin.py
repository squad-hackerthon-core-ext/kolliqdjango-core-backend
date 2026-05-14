from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Transaction
from .models import ReconciliationReport


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'transaction_type', 'amount', 'status',
        'squad_reference', 'created_at'
    ]
    list_filter = ['transaction_type', 'status']
    search_fields = ['user__phone', 'squad_reference', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']

@admin.register(ReconciliationReport)
class ReconciliationReportAdmin(admin.ModelAdmin):
 
    list_display = [
        'ran_at',
        'status_badge',
        'expected_balance_fmt',
        'actual_balance_fmt',
        'drift_fmt',
        'drift_percent_fmt',
        'drift_direction',
    ]
 
    list_filter  = ['status']
    readonly_fields = [
        'id', 'status', 'expected_balance', 'actual_balance',
        'drift', 'drift_percent', 'breakdown', 'error_message',
        'ran_at', 'completed_at', 'created_at', 'drift_direction',
    ]
    ordering = ['-ran_at']
 
    def has_add_permission(self, request):
        return False   # reports are system-generated only
 
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
 
    @admin.display(description='Status')
    def status_badge(self, obj):
        colours = {
            'ok':       '#28a745',
            'critical': '#dc3545',
            'error':    '#fd7e14',
        }
        colour = colours.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px;">{}</span>',
            colour, obj.get_status_display()
        )
 
    @admin.display(description='Expected (₦)')
    def expected_balance_fmt(self, obj):
        if obj.expected_balance is None:
            return '—'
        return f'₦{obj.expected_balance:,.2f}'
 
    @admin.display(description='Actual (₦)')
    def actual_balance_fmt(self, obj):
        if obj.actual_balance is None:
            return '—'
        return f'₦{obj.actual_balance:,.2f}'
 
    @admin.display(description='Drift (₦)')
    def drift_fmt(self, obj):
        if obj.drift is None:
            return '—'
        colour = '#28a745' if obj.drift >= 0 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">₦{:+,.2f}</span>',
            colour, obj.drift
        )
 
    @admin.display(description='Drift %')
    def drift_percent_fmt(self, obj):
        if obj.drift_percent is None:
            return '—'
        return f'{obj.drift_percent:.2f}%'
