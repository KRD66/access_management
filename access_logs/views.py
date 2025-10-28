# access_logs/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse        
from django.contrib import messages          
from django.utils import timezone

from .models import AccessLog
from users.models import UserProfile        


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


@login_required
def test_voice(request):
    """
    Called from the browser when the user speaks a phrase.
    Returns JSON so the front-end can refresh the dashboard.
    """
    if request.method != 'POST':
        return redirect('dashboard')

    # Get the spoken phrase (lowercased for case-insensitive match)
    phrase = request.POST.get('voice_phrase', '').strip().lower()

    profile = UserProfile.objects.filter(
        voice_phrase__iexact=phrase
    ).first()

    success = profile is not None
    notes = f"Voice command: '{phrase}' → {'Granted' if success else 'Denied'}"

    # Create the log entry
    AccessLog.objects.create(
        user_profile=profile,
        device="Browser",
        method='voice',
        result='success' if success else 'failure',
        notes=notes,
    )

    # Optional flash message (shows after reload)
    if success:
        messages.success(request, f"Access granted to {profile.user.username}!")
    else:
        messages.error(request, "Voice phrase not recognized.")

    # Return JSON – the JS will reload the page
    return JsonResponse({'status': 'ok'})