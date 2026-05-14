from rest_framework import serializers
from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    """Read serializer — returned on all user responses."""

    class Meta:
        model = User
        fields = [
            'id',
            'phone',
            'full_name',
            'email',
            'role',
            'gender',
            'date_of_birth',
            'address',
            'location_area',
            'location_city',
            'location_lat',
            'location_lng',
            'skills',
            'languages',
            'has_vehicle',
            'vehicle_type',
            'availability',
            'trade_category',
            'market_name',
            'weekly_income_range',
            'business_name',
            'channel',
            'is_active',
            'is_verified',
            'onboarding_complete',
            'squad_account_number',
            'squad_bank_name',
            'squad_account_status',
            'squad_account_created_at',
            'last_login',
            'created_at',
        ]
        read_only_fields = fields  # This serializer is read-only


class UserCreateSerializer(serializers.Serializer):
    """Write serializer — validates incoming data for user creation."""

    phone = serializers.CharField(max_length=20)
    full_name = serializers.CharField(max_length=255, required=False, default='')
    email = serializers.EmailField(required=False, allow_null=True)
    role = serializers.ChoiceField(
        choices=[(r.value, r.name) for r in User.Role],
        required=False,
        default=User.Role.WORKER
    )
    gender = serializers.ChoiceField(
        choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
        required=False,
        allow_null=True
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    bvn = serializers.CharField(max_length=11, required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location_area = serializers.CharField(max_length=255, required=False, default='')
    location_city = serializers.CharField(max_length=255, required=False, default='Lagos')
    skills = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    languages = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    has_vehicle = serializers.BooleanField(required=False, default=False)
    vehicle_type = serializers.CharField(max_length=50, required=False, default='none')
    availability = serializers.ChoiceField(
        choices=[(a.value, a.name) for a in User.Availability],
        required=False,
        default=User.Availability.FULL_DAY
    )
    trade_category = serializers.CharField(max_length=255, required=False, default='')
    market_name = serializers.CharField(max_length=255, required=False, default='')
    weekly_income_range = serializers.CharField(max_length=100, required=False, default='')
    business_name = serializers.CharField(max_length=255, required=False, default='')
    channel = serializers.CharField(max_length=50, required=False, default='app')
    pin = serializers.CharField(min_length=4, max_length=6, write_only=True, required=False)

    def validate_phone(self, value):
        # Normalise: strip spaces, ensure it starts with a digit or +
        value = value.strip().replace(' ', '')
        if not value:
            raise serializers.ValidationError("Phone number cannot be empty.")
        return value

    def validate_bvn(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError("BVN must contain only digits.")
        if value and len(value) != 11:
            raise serializers.ValidationError("BVN must be exactly 11 digits.")
        return value


class LoginSerializer(serializers.Serializer):

    """Validates login credentials (phone + PIN)."""

    phone = serializers.CharField(max_length=20)
    pin = serializers.CharField(min_length=4, max_length=6, write_only=True)

    def validate_phone(self, value):
        return value.strip().replace(' ', '')

    def validate_pin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("PIN must contain digits only.")
        return value

class ChangePinSerializer(serializers.Serializer):
    """Authenticated user changing their own PIN — requires old PIN for verification."""
    current_pin = serializers.CharField(
        min_length=4,
        max_length=6,
        write_only=True,
    )
    new_pin = serializers.CharField(
        min_length=4,
        max_length=6,
        write_only=True,
    )
    confirm_new_pin = serializers.CharField(
        min_length=4,
        max_length=6,
        write_only=True,
    )
 
    def validate(self, attrs):
        if attrs['new_pin'] != attrs['confirm_new_pin']:
            raise serializers.ValidationError({
                'confirm_new_pin': 'New PIN and confirm PIN do not match.'
            })
        if attrs['current_pin'] == attrs['new_pin']:
            raise serializers.ValidationError({
                'new_pin': 'New PIN must be different from your current PIN.'
            })
        return attrs
 
 
class ResetPinRequestSerializer(serializers.Serializer):
    """Step 1 — request a reset OTP via phone number."""
    phone = serializers.CharField(max_length=20)
 
    def validate_phone(self, value):
        value = value.strip()
        if value.startswith('0'):
            value = '+234' + value[1:]
        return value
 
 
class ResetPinConfirmSerializer(serializers.Serializer):
    """Step 2 — verify OTP and set a new PIN."""
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(min_length=4, max_length=8, write_only=True)
    new_pin = serializers.CharField(min_length=4, max_length=6, write_only=True)
    confirm_new_pin = serializers.CharField(min_length=4, max_length=6, write_only=True)
 
    def validate_phone(self, value):
        value = value.strip()
        if value.startswith('0'):
            value = '+234' + value[1:]
        return value
 
    def validate(self, attrs):
        if attrs['new_pin'] != attrs['confirm_new_pin']:
            raise serializers.ValidationError({
                'confirm_new_pin': 'New PIN and confirm PIN do not match.'
            })
        return attrs
