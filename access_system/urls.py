from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from django.conf import settings
from devices.views import voice_test
from django.views.generic import RedirectView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('devices/', include('devices.urls')),
    path('access_logs/', include('access_logs.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('voice-test/', voice_test, name='voice_test'),
    
    path('voice-test/', include('devices.urls')),
    path('', RedirectView.as_view(url='/login/', permanent=False)),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

