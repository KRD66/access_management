from django.urls import path
from . import views

urlpatterns = [
    path('api/verify_fingerprint/', views.verify_fingerprint, name='verify_fingerprint'),
]