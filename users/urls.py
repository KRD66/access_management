from django.urls import path
from . import views

urlpatterns = [
    path('admin-login/', views.admin_login, name='admin_login'),
    path('entry/', views.entry_gate, name='entry'),
    path('enroll/', views.enroll_user, name='enroll_user'),
]