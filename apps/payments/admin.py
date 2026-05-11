from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Transaction


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