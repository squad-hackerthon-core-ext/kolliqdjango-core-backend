from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        'phone', 'full_name', 'role', 'location_city',
        'is_verified', 'is_flagged', 'onboarding_complete', 'created_at'
    ]
    list_filter = ['role', 'is_verified', 'is_flagged', 'channel', 'location_city']
    search_fields = ['phone', 'full_name', 'business_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        ('Identity', {'fields': ('id', 'phone', 'full_name', 'role', 'channel')}),
        ('Location', {'fields': ('location_area', 'location_city', 'location_lat', 'location_lng')}),
        ('Worker Profile', {'fields': ('skills', 'languages', 'has_vehicle', 'vehicle_type', 'availability')}),
        ('Trader Profile', {'fields': ('trade_category', 'market_name', 'weekly_income_range')}),
        ('Employer Profile', {'fields': ('business_name',)}),
        ('Status', {'fields': ('is_active', 'is_verified', 'is_flagged', 'flag_reason', 'onboarding_complete')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'role', 'password1', 'password2'),
        }),
    )