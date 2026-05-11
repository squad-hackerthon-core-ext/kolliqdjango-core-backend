from django.urls import path
from apps.users.views import (
    UserCreateView,
    LoginView,
    LogoutView,
    TokenRefreshView,
    UserDetailView,
    UserUpdateView,
    UserProfileView,
    OnboardingCompleteView,
    OnboardingStatusView,
    UserVirtualAccountView,
)

urlpatterns = [
    # ------------------------------------------------------------------ #
    #  Auth
    # ------------------------------------------------------------------ #
    path('auth/register/',      UserCreateView.as_view(),  name='user-register'),
    path('auth/login/',         LoginView.as_view(),       name='user-login'),
    path('auth/logout/',        LogoutView.as_view(),      name='user-logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # ------------------------------------------------------------------ #
    #  User CRUD
    # ------------------------------------------------------------------ #
    path('users/',                       UserDetailView.as_view(), name='user-detail-by-phone'),
    path('users/<uuid:user_id>/',        UserDetailView.as_view(), name='user-detail'),
    path('users/<uuid:user_id>/update/', UserUpdateView.as_view(), name='user-update'),
    path('users/<uuid:user_id>/profile/', UserProfileView.as_view(), name='user-profile'),

    # ------------------------------------------------------------------ #
    #  Onboarding
    # ------------------------------------------------------------------ #
    path('users/<uuid:user_id>/onboarding/complete/', OnboardingCompleteView.as_view(), name='onboarding-complete'),
    path('users/<uuid:user_id>/onboarding/status/',   OnboardingStatusView.as_view(),   name='onboarding-status'),

    # ------------------------------------------------------------------ #
    #  Virtual account
    # ------------------------------------------------------------------ #
    path('users/<uuid:user_id>/virtual-account/', UserVirtualAccountView.as_view(), name='user-virtual-account'),
]