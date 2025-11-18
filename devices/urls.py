from django.urls import path
from . import views

urlpatterns = [
    path('api/verify_fingerprint/', views.verify_fingerprint, name='verify_fingerprint'),
    path('list/', views.device_list, name='device_list'),
    path('api/verify_voice_web/', views.verify_voice_web, name='verify_voice_web'),
    path('voice-test/', views.voice_test, name='voice_test'),
]