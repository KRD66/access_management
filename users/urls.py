
# users/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('enroll/', views.enroll_anyone, name='enroll_anyone'),
    path('login/', views.voice_login, name='voice_login'),
]