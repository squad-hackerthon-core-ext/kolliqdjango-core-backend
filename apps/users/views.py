import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated , AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.users.models import User
from apps.users.serializers import UserSerializer, UserCreateSerializer, LoginSerializer
from apps.wallets.models import Wallet
from services.squad import SquadService, SquadAPIError

logger = logging.getLogger(__name__)


def get_tokens_for_user(user):
    """Generate a JWT access + refresh token pair for the given user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


class UserCreateView(APIView):
    permission_classes = [AllowAny]  # Allow anyone to create an account
    """Create a new user with SQUAD virtual account creation."""

    @extend_schema(
        operation_id='users_create',
        summary='Create new user',
        description='Create a new user account with optional SQUAD virtual account provisioning.',
        request=UserCreateSerializer,
        responses={
            201: OpenApiExample(
                'User Created',
                value={
                    'code': 201,
                    'success': True,
                    'message': 'User created successfully',
                    'data': {
                        'tokens': {
                            'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                            'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
                        },
                        'user': {
                            'id': '550e8400-e29b-41d4-a716-446655440000',
                            'phone': '+2348012345678',
                            'full_name': 'John Doe',
                            'role': 'worker'
                        }
                    }
                }
            ),
            200: OpenApiExample(
                'User Exists',
                value={
                    'code': 200,
                    'success': True,
                    'message': 'User already exists',
                    'data': {
                        'id': '550e8400-e29b-41d4-a716-446655440000',
                        'phone': '+2348012345678',
                        'full_name': 'John Doe'
                    }
                }
            ),
            400: OpenApiExample(
                'Validation Error',
                value={
                    'code': 400,
                    'success': False,
                    'message': 'Validation error',
                    'errors': {
                        'phone': ['This field is required.']
                    }
                }
            )
        },
        tags=['Users']
    )
    def post(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'code': 400,
                'success': False,
                'message': 'Validation error',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        phone = data['phone']

        existing_user = User.objects.filter(phone=phone).first()

        if existing_user:
            user_serializer = UserSerializer(existing_user)
            return Response({
                'code': 200,
                'success': True,
                'message': 'User already exists',
                'data': user_serializer.data
            }, status=status.HTTP_200_OK)

        try:
            with transaction.atomic():
                full_name = data.get('full_name', '')
                name_parts = full_name.split(' ', 1)
                first_name = name_parts[0] if name_parts else ''
                last_name = name_parts[1] if len(name_parts) > 1 else ''

                dob = ''
                if data.get('date_of_birth'):
                    dob = data['date_of_birth'].strftime('%m/%d/%Y')

                gender = '1'
                if data.get('gender') == 'F':
                    gender = '2'
                elif data.get('gender') == 'O':
                    gender = '1'

                user = User.objects.create(
                    phone=phone,
                    full_name=full_name,
                    role=data.get('role', User.Role.WORKER),
                    email=data.get('email'),
                    date_of_birth=data.get('date_of_birth'),
                    bvn=data.get('bvn'),
                    gender=data.get('gender'),
                    address=data.get('address'),
                    location_area=data.get('location_area', ''),
                    location_city=data.get('location_city', 'Lagos'),
                    skills=data.get('skills', []),
                    languages=data.get('languages', []),
                    has_vehicle=data.get('has_vehicle', False),
                    vehicle_type=data.get('vehicle_type', 'none'),
                    availability=data.get('availability', User.Availability.FULL_DAY),
                    trade_category=data.get('trade_category', ''),
                    market_name=data.get('market_name', ''),
                    weekly_income_range=data.get('weekly_income_range', ''),
                    business_name=data.get('business_name', ''),
                    channel=data.get('channel', 'app'),
                    is_active=True,
                    onboarding_complete=False,
                )

                if data.get('pin'):
                    user.set_pin(data['pin'])
                    user.save()

                wallet = Wallet.objects.create(user=user, balance=0, escrow_balance=0)

                try:
                    squad_service = SquadService()
                    squad_response = squad_service.create_virtual_account(
                        customer_identifier=str(user.id),
                        first_name=first_name or full_name[:50] or phone,
                        last_name=last_name or 'User',
                        middle_name='',
                        phone=phone,
                        email=data.get('email', f"{phone}@kolliq.ng"),
                        dob=dob,
                        bvn=data.get('bvn', ''),
                        gender=gender,
                        address=data.get('address', ''),
                    )

                    user.squad_account_number = squad_response.get('virtual_account_number')
                    user.squad_bank_name = squad_response.get('bank_name', 'GTBank')
                    user.squad_account_status = 'active'
                    user.squad_account_created_at = timezone.now()
                    user.save()

                    wallet.virtual_account_number = squad_response.get('virtual_account_number')
                    wallet.bank_code = squad_response.get('bank_code', '058')
                    wallet.save()

                    logger.info(f"Squad VA created for user {user.id}: {user.squad_account_number}")

                except SquadAPIError as e:
                    logger.error(f"Squad VA creation failed for user {user.id}: {str(e)}")
                    user.squad_account_status = 'failed'
                    user.save()

                tokens = get_tokens_for_user(user)
                user_serializer = UserSerializer(user)

                return Response({
                    'code': 201,
                    'success': True,
                    'message': 'User created successfully',
                    'data': {
                        'tokens': tokens,
                        'user': user_serializer.data,
                    }
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}", exc_info=True)
            return Response({
                'code': 500,
                'success': False,
                'message': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginView(APIView):
    permission_classes = [AllowAny]  # Allow anyone to attempt login
    """Authenticate a user by phone + PIN. Returns JWT access & refresh tokens."""

    @extend_schema(
        operation_id='users_login',
        summary='User login',
        description='Authenticate user with phone number and PIN. Returns JWT access and refresh tokens.',
        request=LoginSerializer,
        responses={
            200: OpenApiExample(
                'Login Successful',
                value={
                    'code': 200,
                    'success': True,
                    'message': 'Login successful',
                    'data': {
                        'tokens': {
                            'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                            'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
                        },
                        'user': {
                            'id': '550e8400-e29b-41d4-a716-446655440000',
                            'phone': '+2348012345678',
                            'full_name': 'John Doe',
                            'role': 'worker'
                        }
                    }
                }
            ),
            401: OpenApiExample(
                'Invalid PIN',
                value={
                    'code': 401,
                    'success': False,
                    'message': 'Invalid PIN'
                }
            ),
            404: OpenApiExample(
                'User Not Found',
                value={
                    'code': 404,
                    'success': False,
                    'message': 'No account found with this phone number'
                }
            )
        },
        tags=['Users']
    )
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'code': 400,
                'success': False,
                'message': 'Validation error',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data['phone']
        pin = serializer.validated_data['pin']

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response({
                'code': 404,
                'success': False,
                'message': 'No account found with this phone number'
            }, status=status.HTTP_404_NOT_FOUND)

        if not user.is_active:
            return Response({
                'code': 403,
                'success': False,
                'message': 'Your account has been deactivated. Please contact support.'
            }, status=status.HTTP_403_FORBIDDEN)

        if not user.check_pin(pin):
            logger.warning(f"Failed login attempt for phone: {phone}")
            return Response({
                'code': 401,
                'success': False,
                'message': 'Invalid PIN'
            }, status=status.HTTP_401_UNAUTHORIZED)

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        tokens = get_tokens_for_user(user)
        user_serializer = UserSerializer(user)

        logger.info(f"User {user.id} logged in successfully")

        return Response({
            'code': 200,
            'success': True,
            'message': 'Login successful',
            'data': {
                'tokens': tokens,
                'user': user_serializer.data,
            }
        }, status=status.HTTP_200_OK)


class TokenRefreshView(APIView):
    """
    Exchange a valid refresh token for a new access token.
    Body: { "refresh": "<refresh_token>" }
    """
    permission_classes = [AllowAny]  # Allow anyone to refresh their token

    @extend_schema(
        operation_id='users_token_refresh',
        summary='Refresh access token',
        description='Exchange a valid refresh token for a new access token.',
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiExample(
                'Token Refreshed',
                value={
                    'code': 200,
                    'success': True,
                    'message': 'Token refreshed successfully',
                    'data': {
                        'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                        'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
                    }
                }
            ),
            401: OpenApiExample(
                'Invalid Token',
                value={
                    'code': 401,
                    'success': False,
                    'message': 'Invalid or expired refresh token'
                }
            )
        },
        tags=['Users']
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response({
                'code': 400,
                'success': False,
                'message': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            refresh = RefreshToken(refresh_token)
            return Response({
                'code': 200,
                'success': True,
                'message': 'Token refreshed successfully',
                'data': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
            }, status=status.HTTP_200_OK)

        except TokenError:
            return Response({
                'code': 401,
                'success': False,
                'message': 'Invalid or expired refresh token'
            }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """
    Blacklist the refresh token, effectively logging the user out.
    Body: { "refresh": "<refresh_token>" }
    Header: Authorization: Bearer <access_token>
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='users_logout',
        summary='User logout',
        description='Logout user by blacklisting their refresh token. Requires authentication.',
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiExample(
                'Logout Successful',
                value={
                    'code': 200,
                    'success': True,
                    'message': 'Logged out successfully'
                }
            ),
            400: OpenApiExample(
                'Missing Token',
                value={
                    'code': 400,
                    'success': False,
                    'message': 'Refresh token is required to logout'
                }
            ),
            401: OpenApiExample(
                'Invalid Token',
                value={
                    'code': 401,
                    'success': False,
                    'message': 'Invalid or expired refresh token'
                }
            )
        },
        tags=['Users']
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response({
                'code': 400,
                'success': False,
                'message': 'Refresh token is required to logout'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            logger.info(f"User {request.user.id} logged out successfully")
            return Response({
                'code': 200,
                'success': True,
                'message': 'Logged out successfully'
            }, status=status.HTTP_200_OK)

        except TokenError:
            return Response({
                'code': 401,
                'success': False,
                'message': 'Invalid or expired refresh token'
            }, status=status.HTTP_401_UNAUTHORIZED)


class UserDetailView(APIView):
    permission_classes = [AllowAny]
    """Get user details by phone number or user ID."""

    @extend_schema(
        operation_id='users_detail',
        summary='Get user details',
        description='Retrieve user details by user ID or phone number.',
        parameters=[
            OpenApiParameter(
                name='user_id',
                location=OpenApiParameter.PATH,
                description='User UUID',
                required=False,
                type=OpenApiTypes.UUID,
                examples=[
                    OpenApiExample(
                        'User ID',
                        value='550e8400-e29b-41d4-a716-446655440000'
                    )
                ]
            ),
            OpenApiParameter(
                name='phone',
                location=OpenApiParameter.QUERY,
                description='User phone number in E.164 format',
                required=False,
                type=OpenApiTypes.STR,
                examples=[
                    OpenApiExample(
                        'Phone Number',
                        value='+2348012345678'
                    )
                ]
            ),
        ],
        responses={
            200: OpenApiExample(
                'User Found',
                value={
                    'code': 200,
                    'success': True,
                    'data': {
                        'id': '550e8400-e29b-41d4-a716-446655440000',
                        'phone': '+2348012345678',
                        'full_name': 'John Doe',
                        'role': 'worker'
                    }
                }
            ),
            400: OpenApiExample(
                'Missing Parameters',
                value={
                    'code': 400,
                    'success': False,
                    'message': 'Either user_id or phone is required'
                }
            ),
            404: OpenApiExample(
                'User Not Found',
                value={
                    'code': 404,
                    'success': False,
                    'message': 'User not found'
                }
            )
        },
        tags=['Users']
    )
    def get(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        phone = request.query_params.get('phone')

        try:
            if user_id:
                user = User.objects.get(id=user_id)
            elif phone:
                user = User.objects.get(phone=phone)
            else:
                return Response({
                    'code': 400,
                    'success': False,
                    'message': 'Either user_id or phone is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            serializer = UserSerializer(user)
            return Response({
                'code': 200,
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'code': 404,
                'success': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching user: {str(e)}")
            return Response({
                'code': 500,
                'success': False,
                'message': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserUpdateView(APIView):
    permission_classes = [AllowAny]  # Allow anyone to update user information
    """Update user information."""

    @extend_schema(
        operation_id='users_update',
        summary='Update user',
        description='Update user profile information. Only authenticated user can update their own profile.',
        parameters=[
            OpenApiParameter(
                name='user_id',
                location=OpenApiParameter.PATH,
                description='User UUID',
                required=True,
                type=OpenApiTypes.UUID,
                examples=[
                    OpenApiExample(
                        'User ID',
                        value='550e8400-e29b-41d4-a716-446655440000'
                    )
                ]
            ),
        ],
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiExample(
                'User Updated',
                value={
                    'code': 200,
                    'success': True,
                    'message': 'User updated successfully',
                    'data': {
                        'id': '550e8400-e29b-41d4-a716-446655440000',
                        'phone': '+2348012345678',
                        'full_name': 'Jane Doe',
                        'location_area': 'Lekki'
                    }
                }
            ),
            404: OpenApiExample(
                'User Not Found',
                value={
                    'code': 404,
                    'success': False,
                    'message': 'User not found'
                }
            )
        },
        tags=['Users']
    )
    def patch(self, request, user_id, *args, **kwargs):
        try:
            user = User.objects.get(id=user_id)

            allowed_fields = [
                'full_name', 'location_area', 'location_city', 'location_lat', 'location_lng',
                'skills', 'languages', 'has_vehicle', 'vehicle_type', 'availability',
                'trade_category', 'market_name', 'weekly_income_range', 'business_name',
                'email', 'date_of_birth', 'bvn', 'gender', 'address',
                'onboarding_complete', 'is_verified'
            ]

            for field in allowed_fields:
                if field in request.data:
                    setattr(user, field, request.data[field])

            user.save()

            serializer = UserSerializer(user)
            return Response({
                'code': 200,
                'success': True,
                'message': 'User updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'code': 404,
                'success': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            return Response({
                'code': 500,
                'success': False,
                'message': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserProfileView(APIView):
    permission_classes = [AllowAny]
    """Get complete user profile including wallet and stats."""

    @extend_schema(
        operation_id='users_profile',
        summary='Get user profile',
        description='Retrieve comprehensive user profile including wallet and activity statistics.',
        parameters=[
            OpenApiParameter(
                name='user_id',
                location=OpenApiParameter.PATH,
                description='User UUID',
                required=True,
                type=OpenApiTypes.UUID,
                examples=[
                    OpenApiExample(
                        'User ID',
                        value='550e8400-e29b-41d4-a716-446655440000'
                    )
                ]
            ),
        ],
        responses={
            200: OpenApiExample(
                'Profile Retrieved',
                value={
                    'code': 200,
                    'success': True,
                    'data': {
                        'user': {
                            'id': '550e8400-e29b-41d4-a716-446655440000',
                            'phone': '+2348012345678',
                            'full_name': 'John Doe',
                            'role': 'worker'
                        },
                        'wallet': {
                            'balance': '5000.00',
                            'escrow_balance': '1000.00',
                            'virtual_account_number': '0700123456789',
                            'bank_name': 'GTBank'
                        },
                        'stats': {
                            'total_jobs_posted': 5,
                            'total_jobs_completed': 3,
                            'active_contracts': 1
                        }
                    }
                }
            ),
            404: OpenApiExample(
                'User Not Found',
                value={
                    'code': 404,
                    'success': False,
                    'message': 'User not found'
                }
            )
        },
        tags=['Users']
    )
    def get(self, request, user_id, *args, **kwargs):
        try:
            user = User.objects.get(id=user_id)
            user_serializer = UserSerializer(user)

            wallet = Wallet.objects.filter(user=user).first()
            wallet_data = {
                'balance': str(wallet.balance) if wallet else '0',
                'escrow_balance': str(wallet.escrow_balance) if wallet else '0',
                'virtual_account_number': wallet.virtual_account_number if wallet else None,
                'bank_name': wallet.bank_name if wallet else None,
            }

            from apps.jobs.models import Job
            from apps.marketplace.models import Contract
            from django.db import models as django_models

            stats = {
                'total_jobs_posted': Job.objects.filter(employer=user).count(),
                'total_jobs_completed': Contract.objects.filter(worker=user, status='completed').count(),
                'active_contracts': Contract.objects.filter(
                    django_models.Q(employer=user) | django_models.Q(worker=user),
                    status__in=['active', 'in_progress']
                ).count(),
            }

            return Response({
                'code': 200,
                'success': True,
                'data': {
                    'user': user_serializer.data,
                    'wallet': wallet_data,
                    'stats': stats,
                }
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'code': 404,
                'success': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching user profile: {str(e)}")
            return Response({
                'code': 500,
                'success': False,
                'message': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OnboardingCompleteView(APIView):
    permission_classes = [AllowAny]
    """Mark user onboarding as complete."""

    @extend_schema(
        operation_id='users_onboarding_complete',
        summary='Complete onboarding',
        description='Mark user onboarding as complete. Requires authentication.',
        parameters=[
            OpenApiParameter(
                name='user_id',
                location=OpenApiParameter.PATH,
                description='User UUID',
                required=True,
                type=OpenApiTypes.UUID,
                examples=[
                    OpenApiExample(
                        'User ID',
                        value='550e8400-e29b-41d4-a716-446655440000'
                    )
                ]
            ),
        ],
        responses={
            200: OpenApiExample(
                'Onboarding Completed',
                value={
                    'code': 200,
                    'success': True,
                    'message': 'Onboarding completed successfully'
                }
            ),
            404: OpenApiExample(
                'User Not Found',
                value={
                    'code': 404,
                    'success': False,
                    'message': 'User not found'
                }
            )
        },
        tags=['Users']
    )
    def post(self, request, user_id, *args, **kwargs):
        try:
            user = User.objects.get(id=user_id)
            user.onboarding_complete = True
            user.save()

            return Response({
                'code': 200,
                'success': True,
                'message': 'Onboarding completed successfully'
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'code': 404,
                'success': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error completing onboarding: {str(e)}")
            return Response({
                'code': 500,
                'success': False,
                'message': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OnboardingStatusView(APIView):
    permission_classes = [AllowAny]
    """Get onboarding status."""

    def get(self, request, user_id, *args, **kwargs):
        try:
            user = User.objects.get(id=user_id)

            return Response({
                'code': 200,
                'success': True,
                'data': {
                    'onboarding_complete': user.onboarding_complete,
                    'is_verified': user.is_verified,
                    'has_virtual_account': bool(user.squad_account_number),
                }
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'code': 404,
                'success': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching onboarding status: {str(e)}")
            return Response({
                'code': 500,
                'success': False,
                'message': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserVirtualAccountView(APIView):
    permission_classes = [AllowAny]
    """Get or create SQUAD virtual account for user."""

    def get(self, request, user_id, *args, **kwargs):
        try:
            user = User.objects.get(id=user_id)

            if user.squad_account_number and user.squad_account_status == 'active':
                return Response({
                    'code': 200,
                    'success': True,
                    'data': {
                        'virtual_account_number': user.squad_account_number,
                        'bank_name': user.squad_bank_name,
                        'account_status': user.squad_account_status,
                    }
                }, status=status.HTTP_200_OK)

            try:
                squad_service = SquadService()
                full_name = user.full_name or f"User_{user.phone[-4:]}"
                name_parts = full_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else 'User'

                dob = ''
                if user.date_of_birth:
                    dob = user.date_of_birth.strftime('%m/%d/%Y')

                gender = '1'
                if user.gender == 'F':
                    gender = '2'

                squad_response = squad_service.create_virtual_account(
                    customer_identifier=str(user.id),
                    first_name=first_name,
                    last_name=last_name,
                    middle_name='',
                    phone=user.phone,
                    email=user.email or f"{user.phone}@kolliq.ng",
                    dob=dob,
                    bvn=user.bvn or '',
                    gender=gender,
                    address=user.address or '',
                )

                user.squad_account_number = squad_response.get('virtual_account_number')
                user.squad_bank_name = squad_response.get('bank_name', 'GTBank')
                user.squad_account_status = 'active'
                user.squad_account_created_at = timezone.now()
                user.save()

                wallet = Wallet.objects.filter(user=user).first()
                if wallet:
                    wallet.virtual_account_number = squad_response.get('virtual_account_number')
                    wallet.bank_code = squad_response.get('bank_code', '058')
                    wallet.save()

                return Response({
                    'code': 201,
                    'success': True,
                    'data': {
                        'virtual_account_number': user.squad_account_number,
                        'bank_name': user.squad_bank_name,
                        'account_status': user.squad_account_status,
                    }
                }, status=status.HTTP_201_CREATED)

            except SquadAPIError as e:
                logger.error(f"Squad VA creation failed for user {user.id}: {str(e)}")
                return Response({
                    'code': 500,
                    'success': False,
                    'message': f"Failed to create virtual account: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except User.DoesNotExist:
            return Response({
                'code': 404,
                'success': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error in virtual account view: {str(e)}")
            return Response({
                'code': 500,
                'success': False,
                'message': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)