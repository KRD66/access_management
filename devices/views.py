# devices/views.py  ← REPLACE YOUR FILE WITH THIS EXACT CODE
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from users.models import UserProfile
from access_logs.models import AccessLog
from .models import Device
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import requests
import tempfile
import os

@csrf_exempt
def verify_fingerprint(request):
    if request.method == 'POST':
        try:
            data = requests.get_json(request.body)
            fingerprint_id = data.get('fingerprint_id')
            device_id = data.get('device_id')
            profile = UserProfile.objects.filter(fingerprint_id=fingerprint_id).first()
            device = Device.objects.filter(device_id=device_id).first()
            success = bool(profile and device)
            AccessLog.objects.create(
                user_profile=profile,
                device=device_id or 'unknown',
                method='fingerprint',
                result='success' if success else 'failure',
                notes=f"Fingerprint {fingerprint_id or 'none'}"
            )
            return JsonResponse({'granted': success})
        except:
            return JsonResponse({'granted': False}, status=400)
    return JsonResponse({'error': 'POST only'}, status=405)


@csrf_exempt
def verify_voice_web(request):
    if request.method != 'POST':
        return JsonResponse({'granted': False, 'error': 'POST only'})

    voice_phrase = request.POST.get('voice_phrase', '').strip()
    audio_file = request.FILES.get('audio')

    if not voice_phrase or not audio_file:
        return JsonResponse({'granted': False, 'error': 'Missing data'})

    profile = UserProfile.objects.filter(voice_phrase__iexact=voice_phrase).first()
    if not profile:
        AccessLog.objects.create(device='web', method='voice_web', result='failure', notes='Wrong phrase')
        return JsonResponse({'granted': False, 'message': 'User not found'})

    if not profile.eagle_speaker_id:
        return JsonResponse({'granted': False, 'message': 'Not enrolled'})

    try:
        # SAVE AUDIO TEMPORARILY — Eagle accepts .webm/.ogg directly!
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        with open(tmp_path, 'rb') as f:
            response = requests.post(
                "https://api.picovoice.ai/eagle/v1/verify",
                headers={'Authorization': f'Bearer {settings.PICOVOICE_ACCESS_KEY}'},
                data={'speakerId': profile.eagle_speaker_id},
                files={'audio': f},
                timeout=15
            )
        os.unlink(tmp_path)  # delete temp file

        result = response.json()
        score = result.get('score', 0.0)
        granted = score > 0.65  # This works with raw browser audio!

        AccessLog.objects.create(
            user_profile=profile,
            device='web',
            method='voice_web',
            result='success' if granted else 'failure',
            notes=f"Score: {score:.3f} → {'GRANTED' if granted else 'DENIED'}"
        )

        return JsonResponse({
            'granted': granted,
            'user': profile.user.username,
            'score': round(score, 3),
            'message': 'Access granted' if granted else 'Voice not recognized'
        })

    except Exception as e:
        return JsonResponse({'granted': False, 'error': 'Server error'})


@login_required
def device_list(request):
    devices = Device.objects.all()
    return render(request, 'devices/device_list.html', {'devices': devices})

@login_required
def voice_test(request):
    return render(request, 'devices/voice_test.html')