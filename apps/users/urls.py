from django.urls import path

from apps.users.views import (
    RegisterView, LoginView, LogoutView,
    MeView, ProfileView, ChangePinView,
    ResetPinRequestView, ResetPinConfirmView,
)

urlpatterns = [
    path("auth/register/",           RegisterView.as_view()),
    path("auth/login/",              LoginView.as_view()),
    path("auth/logout/",             LogoutView.as_view()),
    path("auth/me/",                 MeView.as_view()),
    path("auth/profile/",            ProfileView.as_view()),
    path("auth/change-pin/",         ChangePinView.as_view()),
    path("auth/reset-pin/request/",  ResetPinRequestView.as_view()),
    path("auth/reset-pin/confirm/",  ResetPinConfirmView.as_view()),
]