from django.urls import path
from . import views

urlpatterns = [
    path('enroll/', views.enroll_user, name='enroll_user'),
    path('list/', views.user_list, name='user_list'),
]