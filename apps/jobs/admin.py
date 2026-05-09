from django.contrib import admin
from django.db.models import Avg
from .models import Job, JobApplication, Rating


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'employer', 'skill_required', 'location_city',
        'pay_per_worker', 'status', 'escrow_funded', 'created_at'
    ]
    list_filter = ['status', 'skill_required', 'location_city', 'escrow_funded', 'source_channel']
    search_fields = ['title', 'employer__phone', 'employer__business_name', 'location_area']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employer')


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ['worker', 'job', 'status', 'accepted_at', 'completed_at']
    list_filter = ['status']
    search_fields = ['worker__phone', 'job__title']
    readonly_fields = ['id', 'accepted_at']


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['from_user', 'to_user', 'job', 'stars', 'created_at']
    list_filter = ['stars']
    search_fields = ['from_user__phone', 'to_user__phone']
    readonly_fields = ['id', 'created_at']