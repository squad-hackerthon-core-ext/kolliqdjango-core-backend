from django.urls import path
from . import views

urlpatterns = [
    path('eligible-borrowers/', views.EligibleBorrowersView.as_view(), name='eligible-borrowers'),
    path('score-report/<uuid:user_id>/', views.UserScoreReportView.as_view(), name='score-report'),
    path('summary/', views.PlatformSummaryView.as_view(), name='platform-summary'),
]