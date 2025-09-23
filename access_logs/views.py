from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import AccessLog
from django.utils import timezone

@login_required
def dashboard(request):
    today = timezone.now().date()
    total_today = AccessLog.objects.filter(timestamp__date=today).count()
    failed = AccessLog.objects.filter(result='failure').count()
    recent = AccessLog.objects.order_by('-timestamp')[:5]

    context = {
        'total_today': total_today,
        'failed': failed,
        'recent_logs': recent,
    }
    return render(request, 'access_logs/dashboard.html', context)