from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    # --- List view ---
    list_display = [
        'phone', 'full_name', 'role', 'is_active', 'is_verified',
        'onboarding_complete', 'created_at',
        # removed 'is_flagged' — field doesn't exist on model
    ]
    list_filter = [
        'role', 'is_active',
        # removed 'is_flagged' — field doesn't exist on model
        'is_verified', 'onboarding_complete',
    ]
    search_fields = ['phone', 'full_name', 'email']
    ordering = ['-created_at']

    # --- Detail view ---
    fieldsets = (
        (None, {'fields': ('phone', 'pin')}),
        ('Profile', {'fields': (
            'full_name', 'email', 'role', 'gender',
            'date_of_birth', 'bvn', 'address',
        )}),
        ('Location', {'fields': (
            'location_area', 'location_city', 'location_lat', 'location_lng',
        )}),
        ('Work Profile', {'fields': (
            'skills', 'languages', 'has_vehicle', 'vehicle_type',
            'availability', 'trade_category', 'market_name',
            'weekly_income_range', 'business_name',
        )}),
        ('Squad', {'fields': (
            'squad_account_number', 'squad_bank_name',
            'squad_account_status', 'squad_account_created_at',
        )}),
        ('Permissions', {'fields': (
            'is_active', 'is_verified', 'is_staff', 'is_superuser',
            'onboarding_complete',
        )}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'pin', 'full_name', 'role'),
        }),
    )

    # CRITICAL — remove these entirely, they reference groups/user_permissions
    # which don't exist since you're not using PermissionsMixin
    filter_horizontal = []