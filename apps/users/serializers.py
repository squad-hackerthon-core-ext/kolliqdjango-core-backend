from rest_framework import serializers
from .models import User


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'phone', 'full_name', 'role', 'channel',
            'location_area', 'location_city', 'location_lat', 'location_lng',
            'skills', 'languages', 'has_vehicle', 'vehicle_type', 'availability',
            'trade_category', 'market_name', 'weekly_income_range',
            'business_name',
        ]

    def validate_phone(self, value):
        # Normalise: strip spaces, ensure +234 prefix
        value = value.strip().replace(' ', '')
        if value.startswith('0'):
            value = '+234' + value[1:]
        if not value.startswith('+234'):
            raise serializers.ValidationError('Phone must be a valid Nigerian number.')
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    economic_score = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    unlocked_services = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'phone', 'full_name', 'role', 'channel',
            'location_area', 'location_city',
            'skills', 'languages', 'has_vehicle', 'vehicle_type', 'availability',
            'trade_category', 'market_name',
            'business_name',
            'is_verified', 'onboarding_complete',
            'economic_score', 'wallet_balance', 'unlocked_services',
            'created_at',
        ]

    def get_economic_score(self, obj):
        try:
            return obj.economic_score.score
        except Exception:
            return 0

    def get_wallet_balance(self, obj):
        try:
            return str(obj.wallet.balance)
        except Exception:
            return '0.00'

    def get_unlocked_services(self, obj):
        from apps.scoring.engine import get_unlocked_services
        try:
            score = obj.economic_score.score
            return get_unlocked_services(score)
        except Exception:
            return []


class UserOnboardingSerializer(serializers.ModelSerializer):
    """Used to complete onboarding after account is created."""
    class Meta:
        model = User
        fields = [
            'full_name', 'location_area', 'location_city',
            'location_lat', 'location_lng',
            'skills', 'languages', 'has_vehicle', 'vehicle_type', 'availability',
            'trade_category', 'market_name', 'weekly_income_range',
            'business_name', 'onboarding_complete',
        ]