from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'squad_account_number', 'balance',
        'escrow_balance', 'squad_creation_status', 'created_at'
    ]
    list_filter = ['squad_creation_status']
    search_fields = ['user__phone', 'squad_account_number', 'user__full_name']
    readonly_fields = ['id', 'created_at', 'updated_at']