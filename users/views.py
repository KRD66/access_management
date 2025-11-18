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
@login_required
@user_passes_test(is_admin, login_url='dashboard')
def enroll_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', 'user')
        fingerprint_id = request.POST.get('fingerprint_id', '').strip() or None
        voice_phrase = request.POST.get('voice_phrase', '').strip() or None

        if not username:
            messages.error(request, 'Username is required.')
            return redirect('enroll_user')

        # Create or get user
        user, created = User.objects.get_or_create(username=username)
        user.email = email or f"{username}@access.local"

        # === PASSWORD HANDLING: ONLY FOR ADMINS ===
        if role == 'admin':
            pass1 = request.POST.get('admin_password1', '')
            pass2 = request.POST.get('admin_password2', '')
            
            if not pass1 or pass1 != pass2 or len(pass1) < 8:
                messages.error(request, 'Admin password must be 8+ characters and match.')
                return redirect('enroll_user')
            
            user.set_password(pass1)
            user.is_staff = True
            user.is_superuser = True
            messages.success(request, f'ADMIN CREATED → {username} can now login with password!')
        else:
            user.set_unusable_password()
            user.is_staff = False
            user.is_superuser = False

        user.save()

        # Rest of your code (profile, voiceprint, etc.) — unchanged
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.fingerprint_id = fingerprint_id
        profile.voice_phrase = voice_phrase
        profile.role = role
        profile.is_active = True
        profile.save()
        # === VOICEPRINT ENROLLMENT (unchanged) ===
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

        # Eagle enrollment
        if voiceprints_saved == 3 and settings.PICOVOICE_ACCESS_KEY:
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
                    messages.error(request, f'Eagle error: {response.text}')
            except Exception as e:
                messages.error(request, f'Voice enrollment failed: {e}')

        messages.success(request, f'User {username} enrolled successfully!')
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