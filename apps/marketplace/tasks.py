from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def increment_listing_views(listing_id: str):
    from .models import Listing
    try:
        Listing.objects.filter(id=listing_id).update(
            views_count=__import__('django.db.models', fromlist=['F']).F('views_count') + 1
        )
    except Exception as e:
        logger.error(f"increment_listing_views failed: {e}")


@shared_task
def notify_seller_new_enquiry(enquiry_id: str):
    from .models import Enquiry
    from services.africas_talking import ATService

    try:
        enquiry = Enquiry.objects.select_related(
            'listing', 'listing__seller', 'buyer'
        ).get(id=enquiry_id)
    except Enquiry.DoesNotExist:
        logger.error(f"notify_seller_new_enquiry: Enquiry {enquiry_id} not found")
        return

    seller = enquiry.listing.seller
    buyer_contact = enquiry.buyer_phone or (
        enquiry.buyer.phone if enquiry.buyer else 'a buyer'
    )

    message = (
        f"Kolliq: New enquiry on your listing '{enquiry.listing.title}'. "
        f"From: {buyer_contact}. "
    )
    if enquiry.offered_price:
        message += f"Offer: ₦{enquiry.offered_price}. "
    if enquiry.message:
        message += f"Message: {enquiry.message[:80]}. "

    message += "Reply via the app or call them directly."

    at = ATService()
    at.send_sms(seller.phone, message)
    logger.info(f"Seller {seller.phone} notified of enquiry {enquiry_id}")


@shared_task
def expire_old_listings():
    """
    Runs daily. Marks listings older than 30 days as expired
    unless the seller has renewed them.
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import Listing

    cutoff = timezone.now() - timedelta(days=30)
    expired = Listing.objects.filter(
        status=Listing.Status.ACTIVE,
        created_at__lt=cutoff,
        expires_at__isnull=True,
    )
    count = expired.update(status=Listing.Status.PAUSED)
    logger.info(f"Expired {count} marketplace listings")


@shared_task
def flag_suspicious_listings():
    """
    Hourly sweep. Flags listings with suspicious patterns:
    - Price 0 or negative (already blocked by serializer but double-check)
    - Same seller posted > 5 listings in 1 hour
    - Listing title contains known spam keywords
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Count
    from .models import Listing

    one_hour_ago = timezone.now() - timedelta(hours=1)
    spam_keywords = ['free money', 'whatsapp only', 'send airtime', 'bitcoin', 'ponzi']

    # High-frequency posters
    high_freq = (
        Listing.objects
        .filter(created_at__gte=one_hour_ago, status='active')
        .values('seller_id')
        .annotate(count=Count('id'))
        .filter(count__gt=5)
    )
    for entry in high_freq:
        Listing.objects.filter(
            seller_id=entry['seller_id'],
            created_at__gte=one_hour_ago,
        ).update(is_flagged=True, flag_reason='High frequency posting')
        logger.warning(f"Marketplace fraud flag: seller {entry['seller_id']} posted {entry['count']} listings in 1hr")

    # Spam keywords
    for keyword in spam_keywords:
        flagged = Listing.objects.filter(
            status='active',
            title__icontains=keyword,
            is_flagged=False,
        )
        for listing in flagged:
            listing.is_flagged = True
            listing.flag_reason = f"Spam keyword detected: '{keyword}'"
            listing.save(update_fields=['is_flagged', 'flag_reason'])