from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from kolliq.utils import success_response, error_response
from .serializers import UserCreateSerializer, UserProfileSerializer, UserOnboardingSerializer

User = get_user_model()


class UserCreateView(APIView):
    """
    Called by Node auth service after OTP is verified.
    Creates the Django user and triggers wallet + score creation via signals.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='users_create',
        summary='Create user',
        description='Create new user after OTP verification',
        request=UserCreateSerializer,
        tags=['Users'],
    )
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status=400)

        phone = serializer.validated_data['phone']

        # Idempotent — return existing user if already created
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults=serializer.validated_data
        )

        if not created:
            # Update fields if re-sent
            for attr, value in serializer.validated_data.items():
                setattr(user, attr, value)
            user.save()

        # Issue JWT for the Node service to return to client
        refresh = RefreshToken.for_user(user)

        return success_response({
            'user_id': str(user.id),
            'phone': user.phone,
            'role': user.role,
            'created': created,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        }, status=201 if created else 200)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='user_profile_retrieve',
        summary='Get user profile',
        description='Get current user\'s profile information',
        tags=['Users'],
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return success_response(serializer.data)


class UserOnboardingView(APIView):
    """Complete or update onboarding fields."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='user_onboarding_update',
        summary='Update user onboarding',
        description='Complete or update user onboarding information',
        request=UserOnboardingSerializer,
        tags=['Users'],
    )
    def patch(self, request):
        serializer = UserOnboardingSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if not serializer.is_valid():
            return error_response(serializer.errors)

        serializer.save(onboarding_complete=True)
        return success_response(UserProfileSerializer(request.user).data)