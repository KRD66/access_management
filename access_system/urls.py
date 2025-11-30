from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('devices/', include('devices.urls')),
    path('access_logs/', include('access_logs.urls')),

    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    # Admin login
    path('admin-login/', include('users.urls')),

    # Public entry for users
    path('', RedirectView.as_view(url='/users/entry/', permanent=False)),
]