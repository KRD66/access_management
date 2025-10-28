from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Device
from users.models import UserProfile
from access_logs.models import AccessLog
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@csrf_exempt
def verify_fingerprint(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        fingerprint_id = data.get('fingerprint_id')
        device_id = data.get('device_id')

        profile = UserProfile.objects.filter(fingerprint_id=fingerprint_id).first()
        device = Device.objects.filter(device_id=device_id).first()

        if profile and device:
            success = True
            notes = f"Access granted for {profile.user.username}"
        else:
            success = False
            notes = "Invalid fingerprint or unknown device"

        AccessLog.objects.create(
            user_profile=profile if profile else None,
            device=device_id,
            method='fingerprint',
            result='success' if success else 'failure',
            notes=notes
        )

        return JsonResponse({'granted': success, 'message': notes})

    return JsonResponse({'error': 'POST only'}, status=405)

@login_required
def device_list(request):
    devices = Device.objects.all()
    return render(request, 'devices/device_list.html', {'devices': devices})



