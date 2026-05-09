from django.urls import path
from . import views

urlpatterns = [
    path('feed/', views.JobFeedView.as_view(), name='job-feed'),
    path('create/', views.JobCreateView.as_view(), name='job-create'),
    path('accept/', views.JobAcceptView.as_view(), name='job-accept'),
    path('complete/', views.JobCompleteView.as_view(), name='job-complete'),
    path('mine/', views.MyJobsView.as_view(), name='my-jobs'),
    path('rate/', views.RatingCreateView.as_view(), name='rating-create'),
    path('ratings/<uuid:user_id>/', views.UserRatingsView.as_view(), name='user-ratings'),
    path('<uuid:job_id>/', views.JobDetailView.as_view(), name='job-detail'),
]