# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.models import User
from django.conf import settings
from .models import UserProfile
from django.core.files.base import ContentFile
import base64
import requests
import os

def is_admin(user):
    return user.is_authenticated and user.is_staff

def voice_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip().lower()
        voice_data = request.POST.get('voice_data')

        if not username or not voice_data:
            messages.error(request, "Please enter username and record your voice.")
            return render(request, 'login.html')

        try:
            user = User.objects.get(username__iexact=username)
            profile = user.userprofile

            if not profile.eagle_speaker_id:
                messages.error(request, "No voiceprint enrolled for this user.")
                return render(request, 'login.html')

            # Save temp audio
            _, b64data = voice_data.split(';base64,')
            audio_bytes = base64.b64decode(b64data)
            temp_path = f"/tmp/login_{username}.webm"
            with open(temp_path, 'wb') as f:
                f.write(audio_bytes)

            # Verify with Picovoice
            response = requests.post(
                "https://api.picovoice.ai/eagle/v1/verify",
                headers={'Authorization': f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
                data={'speakerId': profile.eagle_speaker_id},
                files={'audio': open(temp_path, 'rb')}
            )
            os.remove(temp_path)

            if response.status_code == 200 and response.json().get('verified'):
                login(request, user)
                return redirect('access_logs:dashboard')
            else:
                messages.error(request, "Voice not recognized. Try again.")

        except User.DoesNotExist:
            messages.error(request, "User not found.")
        except Exception:
            messages.error(request, "Login failed. Try again.")

        return render(request, 'login.html')

    return render(request, 'login.html')


@login_required
@user_passes_test(is_admin)
def enroll_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        voice_phrase = request.POST.get('voice_phrase', '').strip()
        role = request.POST.get('role', 'user')

        if not username or not voice_phrase:
            messages.error(request, "Username and voice phrase are required.")
            return redirect('enroll_user')

        # Create or update user
        user, _ = User.objects.get_or_create(username=username.lower())
        user.set_unusable_password()
        user.is_staff = (role == 'admin')
        user.is_superuser = (role == 'admin')
        user.save()

        # Setup profile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.voice_phrase = voice_phrase
        profile.role = role
        profile.is_active = True
        # Reset old voiceprints
        profile.voiceprint_sample_1 = None
        profile.voiceprint_sample_2 = None
        profile.voiceprint_sample_3 = None
        profile.eagle_speaker_id = None
        profile.save()

        # Save 3 voice samples
        voice_files = []
        for i in range(1, 4):
            data = request.POST.get(f'voiceprint{i}')
            if data and data.startswith('data:audio'):
                _, b64data = data.split(';base64,')
                audio_bytes = base64.b64decode(b64data)
                filename = f"voice_{username}_{i}.webm"
                file_obj = ContentFile(audio_bytes, name=filename)
                getattr(profile, f'voiceprint_sample_{i}').save(filename, file_obj, save=False)
                voice_files.append(getattr(profile, f'voiceprint_sample_{i}').path)

        if len(voice_files) < 3:
            messages.error(request, "You must record your voice 3 times.")
            return redirect('enroll_user')

        # Enroll with Eagle
        try:
            files = {f'audio{i}': open(p, 'rb') for i, p in enumerate(voice_files, 1)}
            resp = requests.post(
                "https://api.picovoice.ai/eagle/v1/enroll",
                headers={'Authorization': f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
                files=files
            )
            for f in files.values():
                f.close()

            if resp.status_code == 200:
                profile.eagle_speaker_id = resp.json()['speakerId']
                profile.save()
                messages.success(request, f"{username} enrolled successfully! Use voice to login.")
                return redirect('user_list')
            else:
                messages.error(request, "Voice enrollment failed. Try again.")
        except Exception as e:
            messages.error(request, f"Error: {e}")

        return redirect('enroll_user')

    return render(request, 'users/enroll.html')