from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from kolliq.utils import success_response, error_response
from .models import Listing, ListingImage, Enquiry, Category, SavedListing
from .serializers import (
    ListingCreateSerializer, ListingListSerializer, ListingDetailSerializer,
    ListingUpdateSerializer, EnquiryCreateSerializer, EnquirySerializer,
    ListingImageCreateSerializer, CategorySerializer,
)
import logging

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


# ══════════════════════════════════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════════════════════════════════

class CategoryListView(APIView):
    """GET /api/marketplace/categories/ — public, no auth needed"""
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='marketplace_categories_list',
        summary='Get categories',
        description='Get list of active marketplace categories',
        tags=['Marketplace'],
    )
    def get(self, request):
        categories = Category.objects.filter(is_active=True)
        return success_response({
            'categories': CategorySerializer(categories, many=True).data
        })


# ══════════════════════════════════════════════════════════════════
# LISTINGS — BROWSE
# ══════════════════════════════════════════════════════════════════

class ListingFeedView(APIView):
    """
    GET /api/marketplace/listings/
    Public feed — filterable by category, city, search query, price range.
    Featured listings always float to the top.
    No auth required — buyers can browse without logging in.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='marketplace_listings_list',
        summary='Get listings feed',
        description='Get paginated list of active marketplace listings with filters',
        tags=['Marketplace'],
    )
    def get(self, request):
        qs = Listing.objects.filter(
            status=Listing.Status.ACTIVE
        ).select_related('seller', 'category').prefetch_related('images', 'saved_by')

        # Filters
        category_slug = request.query_params.get('category')
        city = request.query_params.get('city')
        search = request.query_params.get('q')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        seller_id = request.query_params.get('seller_id')
        condition = request.query_params.get('condition')

        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        if city:
            qs = qs.filter(location_city__icontains=city)
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(market_name__icontains=search)
            )
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if seller_id:
            qs = qs.filter(seller_id=seller_id)
        if condition:
            qs = qs.filter(condition=condition)

        # Pagination
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page = 1
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE

        total = qs.count()
        listings = qs[start:end]

        return success_response({
            'listings': ListingListSerializer(
                listings, many=True, context={'request': request}
            ).data,
            'total': total,
            'page': page,
            'pages': (total + PAGE_SIZE - 1) // PAGE_SIZE,
        })


class ListingDetailView(APIView):
    """GET /api/marketplace/listings/<id>/ — public"""
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='marketplace_listings_retrieve',
        summary='Get listing details',
        description='Get detailed information for a specific listing',
        tags=['Marketplace'],
    )
    def get(self, request, listing_id):
        listing = get_object_or_404(
            Listing.objects.select_related('seller', 'category').prefetch_related('images'),
            id=listing_id,
            status__in=[Listing.Status.ACTIVE, Listing.Status.PAUSED]
        )

        # Async view increment — don't block the response
        from apps.marketplace.tasks import increment_listing_views
        increment_listing_views.delay(str(listing_id))

        return success_response(
            ListingDetailSerializer(listing, context={'request': request}).data
        )


# ══════════════════════════════════════════════════════════════════
# LISTINGS — MANAGE (seller)
# ══════════════════════════════════════════════════════════════════

class ListingCreateView(APIView):
    """POST /api/marketplace/listings/create/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_listings_create',
        summary='Create listing',
        description='Create a new marketplace listing',
        request=ListingCreateSerializer,
        tags=['Marketplace'],
    )
    def post(self, request):
        serializer = ListingCreateSerializer(
            data=request.data, context={'request': request}
        )
        if not serializer.is_valid():
            return error_response(serializer.errors)

        listing = serializer.save()

        # Recalculate score — creating a listing is a positive signal
        from apps.scoring.tasks import recalculate_score
        recalculate_score.delay(str(request.user.id))

        return success_response(
            ListingDetailSerializer(listing, context={'request': request}).data,
            status=201
        )


class ListingUpdateView(APIView):
    """PATCH /api/marketplace/listings/<id>/update/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_listings_update',
        summary='Update listing',
        description='Update an existing marketplace listing',
        request=ListingUpdateSerializer,
        tags=['Marketplace'],
    )
    def patch(self, request, listing_id):
        listing = get_object_or_404(Listing, id=listing_id, seller=request.user)

        serializer = ListingUpdateSerializer(listing, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(serializer.errors)

        listing = serializer.save()
        return success_response(
            ListingDetailSerializer(listing, context={'request': request}).data
        )


class ListingPurchaseView(APIView):
    """
    POST /api/marketplace/listings/<id>/purchase/
    Buyer purchases a listing using their Kolliq wallet balance.
    Pure internal ledger — no Squad API call.

    Body:
        quantity: integer   (default 1)
        message: string     (optional note to seller)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, listing_id):
        from apps.marketplace.models import Listing, Enquiry
        from apps.payments.models import Transaction
        from django.db import transaction as db_transaction
        from django.shortcuts import get_object_or_404
        from decimal import Decimal

        buyer = request.user
        listing = get_object_or_404(
            Listing, id=listing_id, status='active'
        )

        if listing.seller == buyer:
            return error_response('You cannot purchase your own listing.')

        quantity = int(request.data.get('quantity', 1))
        if quantity < 1:
            return error_response('Quantity must be at least 1.')

        if quantity > listing.quantity_available:
            return error_response(
                f'Only {listing.quantity_available} available.'
            )

        total = listing.price * quantity
        PLATFORM_CUT = (total * Decimal('0.02')).quantize(Decimal('0.01'))
        seller_receives = total - PLATFORM_CUT

        # Check buyer balance
        try:
            buyer_wallet = buyer.wallet
        except Exception:
            return error_response('Your wallet is not ready.', status=404)

        if buyer_wallet.balance < total:
            return error_response(
                f'Insufficient balance. '
                f'Need ₦{total}, you have ₦{buyer_wallet.balance}. '
                f'Top up your wallet first.'
            )

        seller = listing.seller
        try:
            seller_wallet = seller.wallet
        except Exception:
            return error_response("Seller's wallet is not ready.")

        reference = f"MKT-{listing.id}-{buyer.id}"[:40]

        with db_transaction.atomic():
            # Lock both wallets
            buyer_wallet = type(buyer_wallet).objects.select_for_update().get(
                user=buyer
            )
            seller_wallet = type(seller_wallet).objects.select_for_update().get(
                user=seller
            )

            # Re-check after lock
            if buyer_wallet.balance < total:
                return error_response(
                    f'Insufficient balance: ₦{buyer_wallet.balance}.'
                )

            # Debit buyer
            buyer_wallet.debit(total)

            # Credit seller (minus platform cut)
            seller_wallet.credit(seller_receives)

            # Reduce listing quantity
            listing.quantity_available -= quantity
            if listing.quantity_available == 0:
                listing.status = 'sold'
            listing.save(update_fields=[
                'quantity_available', 'status', 'updated_at'
            ])

            # Transaction records
            Transaction.objects.create(
                user=buyer,
                transaction_type=Transaction.Type.DEBIT,
                amount=total,
                status=Transaction.Status.SUCCESS,
                related_user=seller,
                description=f'Purchase: {listing.title} x{quantity}',
                metadata={
                    'type': 'marketplace_purchase',
                    'listing_id': str(listing.id),
                    'quantity': quantity,
                    'reference': reference,
                }
            )
            Transaction.objects.create(
                user=seller,
                transaction_type=Transaction.Type.CREDIT,
                amount=seller_receives,
                status=Transaction.Status.SUCCESS,
                related_user=buyer,
                description=f'Sale: {listing.title} x{quantity}',
                metadata={
                    'type': 'marketplace_sale',
                    'listing_id': str(listing.id),
                    'platform_fee': str(PLATFORM_CUT),
                    'reference': reference,
                }
            )

        # Notify seller
        from services.africas_talking import ATService
        at = ATService()
        at.send_sms(
            seller.phone,
            f"Kolliq: {buyer.display_name} bought {quantity}x "
            f"'{listing.title}' for ₦{seller_receives}. "
            f"Balance: ₦{seller_wallet.balance}."
        )

        # Recalculate seller score
        from apps.scoring.tasks import recalculate_score
        recalculate_score.delay(str(seller.id))

        return success_response({
            'reference': reference,
            'listing': listing.title,
            'quantity': quantity,
            'total_paid': str(total),
            'platform_fee': str(PLATFORM_CUT),
            'seller_received': str(seller_receives),
            'your_new_balance': str(buyer_wallet.balance),
            'status': 'completed',
            'message': (
                f'Purchase complete! ₦{total} paid. '
                f'Contact {seller.display_name} to arrange pickup.'
            ),
        }, status=201)


class ListingDeleteView(APIView):
    """DELETE /api/marketplace/listings/<id>/delete/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_listings_delete',
        summary='Delete listing',
        description='Delete a marketplace listing',
        tags=['Marketplace'],
    )
    def delete(self, request, listing_id):
        listing = get_object_or_404(Listing, id=listing_id, seller=request.user)
        listing.status = Listing.Status.REMOVED
        listing.save(update_fields=['status', 'updated_at'])
        return success_response({'message': 'Listing removed.'})


class MyListingsView(APIView):
    """GET /api/marketplace/listings/mine/ — seller sees their own listings"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_my_listings_list',
        summary='Get my listings',
        description='Get all listings posted by current user',
        tags=['Marketplace'],
    )
    def get(self, request):
        status_filter = request.query_params.get('status')
        qs = Listing.objects.filter(seller=request.user).prefetch_related('images')
        if status_filter:
            qs = qs.filter(status=status_filter)
        qs = qs.order_by('-created_at')
        return success_response({
            'listings': ListingListSerializer(
                qs, many=True, context={'request': request}
            ).data,
            'count': qs.count(),
        })


# ══════════════════════════════════════════════════════════════════
# IMAGES
# ══════════════════════════════════════════════════════════════════

class ListingImageAddView(APIView):
    """
    POST /api/marketplace/listings/<id>/images/
    Frontend uploads image to Cloudflare R2 first, then sends URL here.
    We store the URL — no file processing on Django side.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_listing_images_create',
        summary='Add listing image',
        description='Add image to a listing',
        request=ListingImageCreateSerializer,
        tags=['Marketplace'],
    )
    def post(self, request, listing_id):
        listing = get_object_or_404(Listing, id=listing_id, seller=request.user)
        data = {**request.data, 'listing': str(listing.id)}
        serializer = ListingImageCreateSerializer(
            data=data, context={'request': request}
        )
        if not serializer.is_valid():
            return error_response(serializer.errors)

        # If this is marked primary, clear existing primary
        if serializer.validated_data.get('is_primary'):
            listing.images.filter(is_primary=True).update(is_primary=False)

        image = serializer.save()
        return success_response({
            'image_id': str(image.id),
            'image_url': image.image_url,
            'is_primary': image.is_primary,
        }, status=201)

    @extend_schema(
        operation_id='marketplace_listing_images_delete',
        summary='Delete listing image',
        description='Delete an image from a listing',
        tags=['Marketplace'],
    )
    def delete(self, request, listing_id):
        """DELETE /api/marketplace/listings/<id>/images/?image_id=<id>"""
        image_id = request.query_params.get('image_id')
        if not image_id:
            return error_response('image_id query param required.')
        listing = get_object_or_404(Listing, id=listing_id, seller=request.user)
        image = get_object_or_404(ListingImage, id=image_id, listing=listing)
        image.delete()
        return success_response({'message': 'Image removed.'})


# ══════════════════════════════════════════════════════════════════
# ENQUIRIES
# ══════════════════════════════════════════════════════════════════

class EnquiryCreateView(APIView):
    """POST /api/marketplace/enquiries/ — buyer contacts seller"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_enquiries_create',
        summary='Create enquiry',
        description='Send enquiry to listing seller',
        request=EnquiryCreateSerializer,
        tags=['Marketplace'],
    )
    def post(self, request):
        serializer = EnquiryCreateSerializer(
            data=request.data, context={'request': request}
        )
        if not serializer.is_valid():
            return error_response(serializer.errors)

        enquiry = serializer.save()

        # Notify seller via SMS
        from apps.marketplace.tasks import notify_seller_new_enquiry
        notify_seller_new_enquiry.delay(str(enquiry.id))

        return success_response({
            'enquiry_id': str(enquiry.id),
            'listing_title': enquiry.listing.title,
            'seller_phone': (
                enquiry.listing.seller.phone
                if enquiry.listing.show_phone
                else 'Contact via platform'
            ),
            'message': 'Enquiry sent! The seller will be notified.',
        }, status=201)


class MyEnquiriesView(APIView):
    """GET /api/marketplace/enquiries/mine/ — buyer sees their sent enquiries"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_my_enquiries_list',
        summary='Get my enquiries',
        description='Get enquiries sent by current user',
        tags=['Marketplace'],
    )
    def get(self, request):
        enquiries = Enquiry.objects.filter(
            buyer=request.user
        ).select_related('listing').order_by('-created_at')
        return success_response({
            'enquiries': EnquirySerializer(enquiries, many=True).data,
            'count': enquiries.count(),
        })


class SellerEnquiriesView(APIView):
    """GET /api/marketplace/enquiries/received/ — seller sees incoming enquiries"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_seller_enquiries_list',
        summary='Get received enquiries',
        description='Get enquiries received by current seller',
        tags=['Marketplace'],
    )
    def get(self, request):
        listing_id = request.query_params.get('listing_id')
        qs = Enquiry.objects.filter(
            listing__seller=request.user
        ).select_related('listing').order_by('-created_at')
        if listing_id:
            qs = qs.filter(listing_id=listing_id)
        return success_response({
            'enquiries': EnquirySerializer(qs, many=True).data,
            'count': qs.count(),
        })


class EnquiryRespondView(APIView):
    """PATCH /api/marketplace/enquiries/<id>/respond/ — seller marks responded"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_enquiries_respond',
        summary='Mark enquiry as responded',
        description='Mark enquiry as responded by seller',
        tags=['Marketplace'],
    )
    def patch(self, request, enquiry_id):
        enquiry = get_object_or_404(
            Enquiry,
            id=enquiry_id,
            listing__seller=request.user
        )
        enquiry.status = Enquiry.Status.RESPONDED
        enquiry.save(update_fields=['status', 'updated_at'])
        return success_response({'status': 'responded'})


# ══════════════════════════════════════════════════════════════════
# SAVED LISTINGS
# ══════════════════════════════════════════════════════════════════

class SaveListingView(APIView):
    """POST /api/marketplace/listings/<id>/save/ — toggle save"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_listings_save',
        summary='Save or unsave listing',
        description='Toggle saved status for a listing',
        tags=['Marketplace'],
    )
    def post(self, request, listing_id):
        listing = get_object_or_404(Listing, id=listing_id)
        saved, created = SavedListing.objects.get_or_create(
            user=request.user, listing=listing
        )
        if not created:
            saved.delete()
            return success_response({'saved': False, 'message': 'Removed from saved.'})
        return success_response({'saved': True, 'message': 'Saved!'}, status=201)


class SavedListingsView(APIView):
    """GET /api/marketplace/listings/saved/ — buyer's saved listings"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='marketplace_saved_listings_list',
        summary='Get saved listings',
        description='Get all listings saved by current user',
        tags=['Marketplace'],
    )
    def get(self, request):
        saved = SavedListing.objects.filter(
            user=request.user
        ).select_related('listing__seller', 'listing__category').prefetch_related(
            'listing__images'
        ).order_by('-created_at')
        listings = [s.listing for s in saved if s.listing.status == 'active']
        return success_response({
            'listings': ListingListSerializer(
                listings, many=True, context={'request': request}
            ).data,
            'count': len(listings),
        })