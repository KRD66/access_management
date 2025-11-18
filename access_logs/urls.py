from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('test-voice/', views.test_voice, name='test_voice'),
    
]