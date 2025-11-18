# devices/views.py  ← DEPLOY THIS NOW
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from users.models import UserProfile
from access_logs.models import AccessLog
from .models import Device
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import requests
import json
import tempfile
import wave
import audioop
from django.core.files.uploadedfile import InMemoryUploadedFile
import io

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


def convert_to_16khz_wav(audio_file):
    """Convert any uploaded audio to 16kHz mono WAV (Eagle requirement)"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_in:
        for chunk in audio_file.chunks():
            tmp_in.write(chunk)
        tmp_in_path = tmp_in.name

    with wave.open(tmp_in_path, 'rb') as wav_in:
        params = wav_in.getparams()
        audio_data = wav_in.readframes(params.nframes)

    # Convert to 16kHz mono 16-bit PCM
    audio_16khz = audioop.ratecv(audio_data, 2, params.nchannels, params.framerate, 16000, None)[0]
    if params.nchannels > 1:
        audio_16khz = audioop.tomono(audio_16khz, 2, 1, 1)

    # Write final 16kHz WAV
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(2)
        wav_out.setframerate(16000)
        wav_out.writeframes(audio_16khz)

    output.seek(0)
    return InMemoryUploadedFile(
        output, None, 'voice.wav', 'audio/wav', output.getbuffer().nbytes, None
    )


@csrf_exempt
def verify_voice_web(request):
    if request.method != 'POST':
        return JsonResponse({'granted': False, 'error': 'POST required'}, status=405)

    voice_phrase = request.POST.get('voice_phrase', '').strip()
    audio_file = request.FILES.get('audio')

    if not voice_phrase or not audio_file:
        return JsonResponse({'granted': False, 'error': 'Missing phrase or audio'}, status=400)

    profile = UserProfile.objects.filter(voice_phrase__iexact=voice_phrase).first()

    if not profile:
        AccessLog.objects.create(device='web', method='voice_web', result='failure', notes=f"Phrase not found: {voice_phrase}")
        return JsonResponse({'granted': False, 'message': 'Phrase not recognized'})

    if not profile.eagle_speaker_id:
        AccessLog.objects.create(user_profile=profile, device='web', method='voice_web', result='failure', notes="No Eagle voiceprint")
        return JsonResponse({'granted': False, 'message': 'Voiceprint not enrolled'})

    try:
        # CRITICAL: Convert to 16kHz WAV
        wav_file = convert_to_16khz_wav(audio_file)

        response = requests.post(
            "https://api.picovoice.ai/eagle/v1/verify",
            headers={'Authorization': f'Bearer {settings.PICOVOICE_ACCESS_KEY}'},
            data={'speakerId': profile.eagle_speaker_id},
            files={'audio': ('voice.wav', wav_file, 'audio/wav')},
            timeout=15
        )

        if response.status_code != 200:
            error_msg = response.json().get('error', 'Unknown Eagle error')
            raise Exception(error_msg)

        result = response.json()
        is_match = result.get('isMatch', False)
        score = result.get('score', 0.0)

        # Lower threshold slightly for real-world use
        granted = is_match or score > 0.65

        AccessLog.objects.create(
            user_profile=profile,
            device='web_browser',
            method='voice_web',
            result='success' if granted else 'failure',
            notes=f"Eagle score: {score:.3f} | Match: {is_match} | Granted: {granted}"
        )

        return JsonResponse({
            'granted': granted,
            'user': profile.user.username,
            'score': round(score, 3),
            'message': 'Access granted' if granted else 'Voice not recognized'
        })

    except Exception as e:
        AccessLog.objects.create(user_profile=profile, device='web', method='voice_web', result='failure', notes=f"Error: {str(e)}")
        return JsonResponse({'granted': False, 'error': str(e)}, status=500)


@login_required
def device_list(request):
    devices = Device.objects.all()
    return render(request, 'devices/device_list.html', {'devices': devices})


@login_required
def voice_test(request):
    return render(request, 'devices/voice_test.html')