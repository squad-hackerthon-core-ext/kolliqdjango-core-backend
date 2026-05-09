from rest_framework import serializers
from django.db.models import Avg
from .models import Listing, ListingImage, Enquiry, Category, SavedListing


class CategorySerializer(serializers.ModelSerializer):
    listing_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'listing_count']

    def get_listing_count(self, obj):
        return obj.listings.filter(status='active').count()


class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ['id', 'image_url', 'is_primary', 'upload_order']


class SellerBriefSerializer(serializers.Serializer):
    """Safe public view of a seller — no private fields."""
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    location_area = serializers.CharField()
    location_city = serializers.CharField()
    market_name = serializers.CharField()
    economic_score = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    member_since = serializers.DateTimeField(source='created_at')

    def get_economic_score(self, obj):
        try:
            return obj.economic_score.score
        except Exception:
            return 0

    def get_avg_rating(self, obj):
        avg = obj.ratings_received.aggregate(avg=Avg('stars'))['avg']
        return round(avg, 1) if avg else None


class ListingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = [
            'title', 'description', 'category',
            'price', 'price_type', 'condition',
            'quantity_available', 'unit',
            'location_area', 'location_city',
            'location_lat', 'location_lng', 'market_name',
            'whatsapp_number', 'call_number', 'show_phone',
            'source_channel',
        ]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('Price must be greater than 0.')
        return value

    def validate(self, data):
        user = self.context['request'].user
        if user.role not in ('trader', 'worker', 'employer'):
            raise serializers.ValidationError('Only registered users can create listings.')
        # Max 10 active listings per seller
        active_count = Listing.objects.filter(
            seller=user, status='active'
        ).count()
        if active_count >= 10:
            raise serializers.ValidationError(
                'Maximum 10 active listings. Mark some as sold or paused first.'
            )
        return data

    def create(self, validated_data):
        return Listing.objects.create(
            seller=self.context['request'].user,
            **validated_data
        )


class ListingListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    seller_name = serializers.CharField(source='seller.display_name', read_only=True)
    seller_score = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'price', 'price_type', 'unit',
            'condition', 'location_area', 'location_city',
            'market_name', 'status',
            'views_count', 'enquiries_count',
            'primary_image', 'seller_name', 'seller_score',
            'category_name', 'is_featured', 'is_saved',
            'created_at',
        ]

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        return img.image_url if img else None

    def get_seller_score(self, obj):
        try:
            return obj.seller.economic_score.score
        except Exception:
            return 0

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.saved_by.filter(user=request.user).exists()
        return False


class ListingDetailSerializer(serializers.ModelSerializer):
    images = ListingImageSerializer(many=True, read_only=True)
    seller = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)
    contact_phone = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'description',
            'price', 'price_type', 'condition',
            'quantity_available', 'unit',
            'location_area', 'location_city', 'market_name',
            'location_lat', 'location_lng',
            'status', 'views_count', 'enquiries_count',
            'images', 'seller', 'category',
            'contact_phone', 'show_phone',
            'is_featured', 'is_saved',
            'created_at', 'updated_at',
        ]

    def get_seller(self, obj):
        return SellerBriefSerializer(obj.seller).data

    def get_contact_phone(self, obj):
        if not obj.show_phone:
            return None
        return obj.whatsapp_number or obj.call_number or obj.seller.phone

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.saved_by.filter(user=request.user).exists()
        return False


class ListingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = [
            'title', 'description', 'price', 'price_type',
            'condition', 'quantity_available', 'unit',
            'location_area', 'location_city', 'market_name',
            'whatsapp_number', 'call_number', 'show_phone',
            'status',
        ]


class EnquiryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = ['listing', 'message', 'offered_price', 'buyer_phone']

    def validate(self, data):
        listing = data['listing']
        if listing.status != 'active':
            raise serializers.ValidationError('This listing is no longer available.')
        user = self.context['request'].user
        if listing.seller == user:
            raise serializers.ValidationError('You cannot enquire on your own listing.')
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        enquiry = Enquiry.objects.create(
            buyer=user,
            buyer_phone=validated_data.pop('buyer_phone', '') or user.phone,
            **validated_data
        )
        # Increment counter on listing
        listing = enquiry.listing
        listing.enquiries_count += 1
        listing.save(update_fields=['enquiries_count'])
        return enquiry


class EnquirySerializer(serializers.ModelSerializer):
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    listing_price = serializers.DecimalField(
        source='listing.price', max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Enquiry
        fields = [
            'id', 'listing', 'listing_title', 'listing_price',
            'buyer_phone', 'message', 'offered_price',
            'status', 'created_at',
        ]


class ListingImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ['listing', 'image_url', 'is_primary', 'upload_order']

    def validate(self, data):
        listing = data['listing']
        if listing.images.count() >= 4:
            raise serializers.ValidationError(
                'Maximum 4 images per listing.'
            )
        user = self.context['request'].user
        if listing.seller != user:
            raise serializers.ValidationError(
                'You can only add images to your own listings.'
            )
        return data