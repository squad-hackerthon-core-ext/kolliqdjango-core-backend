from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.UserCreateView.as_view(), name='user-create'),
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('onboarding/', views.UserOnboardingView.as_view(), name='user-onboarding'),
]