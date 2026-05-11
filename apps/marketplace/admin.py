from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Listing, ListingImage, Enquiry, Category, SavedListing


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'seller', 'category', 'price', 'status',
        'is_featured', 'is_flagged', 'views_count', 'enquiries_count', 'created_at'
    ]
    list_filter = ['status', 'category', 'is_featured', 'is_flagged', 'location_city']
    search_fields = ['title', 'seller__phone', 'seller__full_name', 'market_name']
    readonly_fields = ['id', 'views_count', 'enquiries_count', 'created_at', 'updated_at']
    ordering = ['-created_at']
    actions = ['feature_listings', 'unflag_listings', 'remove_listings']

    def feature_listings(self, request, queryset):
        queryset.update(is_featured=True)
    feature_listings.short_description = "Mark as featured"

    def unflag_listings(self, request, queryset):
        queryset.update(is_flagged=False, flag_reason='')
    unflag_listings.short_description = "Clear fraud flag"

    def remove_listings(self, request, queryset):
        queryset.update(status='removed')
    remove_listings.short_description = "Remove selected listings"


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ['listing', 'buyer_phone', 'offered_price', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['listing__title', 'buyer_phone', 'buyer__phone']
    readonly_fields = ['id', 'created_at']


admin.site.register(ListingImage)
admin.site.register(SavedListing)