# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from django.conf import settings
from .models import UserProfile
from django.core.files.base import ContentFile
import base64
import requests
import os

# Admin check
def is_admin(user):
    return user.is_authenticated and user.is_staff

import string
import random




from django.contrib.auth import authenticate, login
from django.http import JsonResponse
import json

def voice_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        voice_data = request.POST.get('voice_data')

        if not username or not voice_data:
            messages.error(request, 'Please enter username and record your voice.')
            return render(request, 'login.html')

        try:
            user = User.objects.get(username=username)
            profile = user.userprofile

            if not profile.eagle_speaker_id:
                messages.error(request, 'No voiceprint enrolled for this user.')
                return render(request, 'login.html')

            # Save voice temporarily
            format_part, b64data = voice_data.split(';base64,')
            audio_bytes = base64.b64decode(b64data)
            temp_path = f"/tmp/login_voice_{username}_{request.session.session_key or 'temp'}.webm"
            with open(temp_path, 'wb') as f:
                f.write(audio_bytes)

            # Verify with Picovoice Eagle
            response = requests.post(
                "https://api.picovoice.ai/eagle/v1/verify",
                headers={'Authorization': f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
                data={'speakerId': profile.eagle_speaker_id},
                files={'audio': open(temp_path, 'rb')}
            )
            os.remove(temp_path)  # clean up

            if response.status_code == 200:
                result = response.json()
                if result.get('verified'):
                    login(request, user)
                    return redirect('access_logs:dashboard')  # or wherever your dashboard is
                else:
                    messages.error(request, 'Voice not recognized. Try again.')
            else:
                messages.error(request, 'Voice verification failed. Try again.')

        except User.DoesNotExist:
            messages.error(request, 'User not found.')
        except Exception as e:
            messages.error(request, 'Login error. Please try again.')
        return render(request, 'login.html')

    # GET request → show login page
    return render(request, 'login.html')
@login_required
@user_passes_test(is_admin, login_url='dashboard')
def enroll_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', 'user')
        fingerprint_id = request.POST.get('fingerprint_id', '').strip() or None
        voice_phrase = request.POST.get('voice_phrase', '').strip()

        if not username:
            messages.error(request, 'Username is required.')
            return redirect('enroll_user')

        if not voice_phrase:
            messages.error(request, 'Voice phrase is required for all users (including admins).')
            return redirect('enroll_user')

        # Create user
        user, created = User.objects.get_or_create(username=username)
        user.email = email or f"{username}@access.local"

        # NO PASSWORDS ANYMORE — EVER
        user.set_unusable_password()  # Everyone uses voice only
        
        if role == 'admin':
            user.is_staff = True
            user.is_superuser = True
            messages.info(request, f'Admin {username} created — voice login only!')
        else:
            user.is_staff = False
            user.is_superuser = False

        user.save()

        # Profile setup
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.fingerprint_id = fingerprint_id
        profile.voice_phrase = voice_phrase
        profile.role = role
        profile.is_active = True
        profile.save()

        # === VOICEPRINT ENROLLMENT (3 recordings REQUIRED) ===
        voiceprint_files = []
        voiceprints_saved = 0

        for i in range(1, 4):
            data = request.POST.get(f'voiceprint{i}')
            if data and data.startswith('data:audio'):
                try:
                    format_part, imgstr = data.split(';base64,')
                    ext = format_part.split('/')[-1]
                    filename = f"voiceprint_{username}_{i}.{ext}"
                    file_content = ContentFile(base64.b64decode(imgstr), name=filename)
                    field_name = f'voiceprint_sample_{i}'
                    getattr(profile, field_name).save(filename, file_content, save=False)
                    voiceprint_files.append(getattr(profile, field_name).path)
                    voiceprints_saved += 1
                except Exception as e:
                    messages.warning(request, f'Voiceprint {i} failed: {e}')

        # REQUIRE 3 voice samples — especially for admins
        if voiceprints_saved < 3:
            messages.error(request, 'You MUST record voice 3 times to complete enrollment.')
            return redirect('enroll_user')

        # Enroll with Picovoice Eagle
        if settings.PICOVOICE_ACCESS_KEY:
            try:
                files = {f'audio{i}': open(path, 'rb') for i, path in enumerate(voiceprint_files, 1)}
                response = requests.post(
                    "https://api.picovoice.ai/eagle/v1/enroll",
                    headers={'Authorization': f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
                    files=files
                )
                for f in files.values():
                    f.close()

                if response.status_code == 200:
                    speaker_id = response.json().get('speakerId')
                    profile.eagle_speaker_id = speaker_id
                    profile.save()
                    messages.success(request, f'Voiceprint enrolled! Speaker ID: {speaker_id}')
                else:
                    messages.error(request, f'Voice enrollment failed: {response.text}')
                    return redirect('enroll_user')
            except Exception as e:
                messages.error(request, f'Voice enrollment failed: {e}')
                return redirect('enroll_user')
        else:
            messages.error(request, 'Picovoice key missing!')
            return redirect('enroll_user')

        messages.success(request, f'{role.title()} "{username}" enrolled successfully — Voice Login Ready!')
        return redirect('user_list')

    return render(request, 'users/enroll.html')
@login_required
def user_list(request):
    profiles = UserProfile.objects.select_related('user').all().order_by('user__username')
    return render(request, 'users/list.html', {'profiles': profiles})

@login_required
@user_passes_test(is_admin, login_url='dashboard')
def delete_user(request, user_id):
    if request.method == 'POST':
        profile = get_object_or_404(UserProfile, user__id=user_id)
        username = profile.user.username
        profile.user.delete()
        messages.success(request, f'User {username} deleted successfully.')
        return redirect('user_list')
    return redirect('user_list')