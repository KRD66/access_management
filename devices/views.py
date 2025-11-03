# devices/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from users.models import UserProfile
from access_logs.models import AccessLog
from .models import Device
import requests
import json

@csrf_exempt
def verify_fingerprint(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            fingerprint_id = data.get('fingerprint_id')
            device_id = data.get('device_id')

            profile = UserProfile.objects.filter(fingerprint_id=fingerprint_id).first()
            device = Device.objects.filter(device_id=device_id).first()

            success = bool(profile and device)
            notes = f"Access {'granted' if success else 'denied'} for fingerprint {fingerprint_id or 'unknown'}"

            AccessLog.objects.create(
                user_profile=profile,
                device=device_id or 'unknown',
                method='fingerprint',
                result='success' if success else 'failure',
                notes=notes
            )

            return JsonResponse({
                'granted': success,
                'message': notes
            })
        except Exception as e:
            return JsonResponse({'granted': False, 'error': str(e)}, status=400)

    return JsonResponse({'error': 'POST only'}, status=405)

@csrf_exempt
def verify_voice_web(request):
    """
    Web browser voice verification using Picovoice Eagle.
    POST: voice_phrase (str), audio (file)
    """
    if request.method != 'POST':
        return JsonResponse({'granted': False, 'error': 'POST required'}, status=405)

    voice_phrase = request.POST.get('voice_phrase', '').strip().lower()
    audio_file = request.FILES.get('audio')

    if not voice_phrase or not audio_file:
        return JsonResponse({'granted': False, 'error': 'Missing phrase or audio'}, status=400)

    # Find user by voice phrase
    profile = UserProfile.objects.filter(
        voice_phrase__iexact=voice_phrase,
        is_active=True
    ).first()

    if not profile:
        AccessLog.objects.create(
            user_profile=None,
            device='web_browser',
            method='voice_web',
            result='failure',
            notes=f"Phrase '{voice_phrase}' not found"
        )
        return JsonResponse({'granted': False, 'message': 'Phrase not recognized'})

    if not profile.eagle_speaker_id:
        AccessLog.objects.create(
            user_profile=profile,
            device='web_browser',
            method='voice_web',
            result='failure',
            notes="Eagle voiceprint not enrolled"
        )
        return JsonResponse({'granted': False, 'message': 'Voiceprint not enrolled'})

    # Send to Picovoice Eagle for verification
    try:
        response = requests.post(
            "https://api.picovoice.ai/eagle/v1/verify",
            headers={
                'Authorization': f"Bearer {settings.PICOVOICE_ACCESS_KEY}"
            },
            data={
                'speakerId': profile.eagle_speaker_id
            },
            files={
                'audio': (audio_file.name, audio_file, audio_file.content_type)
            },
            timeout=10
        )

        if response.status_code != 200:
            error = response.json().get('error', 'Unknown')
            raise Exception(f"Eagle error: {error}")

        result = response.json()
        is_match = result.get('isMatch', False)
        score = result.get('score', 0.0)

        # Log access attempt
        AccessLog.objects.create(
            user_profile=profile,
            device='web_browser',
            method='voice_web',
            result='success' if is_match else 'failure',
            notes=f"Eagle verification: {'Match' if is_match else 'No Match'} (score: {score:.2f})"
        )

        return JsonResponse({
            'granted': is_match,
            'user': profile.user.username,
            'score': score,
            'message': 'Access granted' if is_match else 'Voice not recognized'
        })

    except Exception as e:
        AccessLog.objects.create(
            user_profile=profile,
            device='web_browser',
            method='voice_web',
            result='failure',
            notes=f"Verification error: {str(e)}"
        )
        return JsonResponse({
            'granted': False,
            'error': 'Verification failed',
            'details': str(e)
        }, status=500)

# Keep your device list view
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def device_list(request):
    devices = Device.objects.all()
    return render(request, 'devices/device_list.html', {'devices': devices})