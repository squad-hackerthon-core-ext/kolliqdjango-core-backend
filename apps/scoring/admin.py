from django.contrib import admin
from .models import EconomicIdentityScore


@admin.register(EconomicIdentityScore)
class EconomicIdentityScoreAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'score', 'savings_unlocked',
        'insurance_unlocked', 'loan_unlocked', 'last_calculated'
    ]
    list_filter = ['savings_unlocked', 'insurance_unlocked', 'loan_unlocked']
    search_fields = ['user__phone', 'user__full_name']
    readonly_fields = ['last_calculated', 'created_at']