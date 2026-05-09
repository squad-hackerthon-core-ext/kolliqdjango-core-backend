from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category-list'),

    # Browse
    path('listings/', views.ListingFeedView.as_view(), name='listing-feed'),
    path('listings/mine/', views.MyListingsView.as_view(), name='my-listings'),
    path('listings/saved/', views.SavedListingsView.as_view(), name='saved-listings'),
    path('listings/create/', views.ListingCreateView.as_view(), name='listing-create'),
    path('listings/<uuid:listing_id>/', views.ListingDetailView.as_view(), name='listing-detail'),
    path('listings/<uuid:listing_id>/update/', views.ListingUpdateView.as_view(), name='listing-update'),
    path('listings/<uuid:listing_id>/delete/', views.ListingDeleteView.as_view(), name='listing-delete'),
    path('listings/<uuid:listing_id>/images/', views.ListingImageAddView.as_view(), name='listing-images'),
    path('listings/<uuid:listing_id>/save/', views.SaveListingView.as_view(), name='listing-save'),

    # Enquiries
    path('enquiries/', views.EnquiryCreateView.as_view(), name='enquiry-create'),
    path('enquiries/mine/', views.MyEnquiriesView.as_view(), name='my-enquiries'),
    path('enquiries/received/', views.SellerEnquiriesView.as_view(), name='seller-enquiries'),
    path('enquiries/<uuid:enquiry_id>/respond/', views.EnquiryRespondView.as_view(), name='enquiry-respond'),
]