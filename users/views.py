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

@login_required
@user_passes_test(is_admin, login_url='dashboard')
def enroll_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', 'user')
        fingerprint_id = request.POST.get('fingerprint_id', '').strip() or None
        voice_phrase = request.POST.get('voice_phrase', '').strip() or None

        # Validate
        if not username:
            messages.error(request, 'Username is required.')
            return redirect('enroll_user')

        # Create or update user
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.email = email
            user.set_password('temp123')
            user.save()
            messages.info(request, f'Password set to "temp123" for {username}.')
        else:
            if user.email != email:
                user.email = email
                user.save()

        # Update profile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.fingerprint_id = fingerprint_id
        profile.voice_phrase = voice_phrase
        profile.role = role
        profile.is_active = True
        profile.save()

        # Save voiceprints locally (3 recordings)
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
                    if hasattr(profile, field_name):
                        getattr(profile, field_name).save(filename, file_content, save=False)
                        voiceprint_files.append(getattr(profile, field_name).path)
                        voiceprints_saved += 1
                except Exception as e:
                    messages.warning(request, f'Voiceprint {i} failed to save: {e}')

        # Send to Picovoice Rhino to create voiceprint
        voiceprint_id = None
        if voiceprints_saved == 3 and voice_phrase and settings.PICOVOICE_ACCESS_KEY:
            try:
                files = {}
                for i, path in enumerate(voiceprint_files, 1):
                    files[f'sample{i}'] = open(path, 'rb')

                response = requests.post(
                    "https://api.picovoice.ai/rhino/v1/enroll",
                    headers={'Authorization': f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
                    data={'phrase': voice_phrase},
                    files=files
                )

                for f in files.values():
                    f.close()

                if response.status_code == 200:
                    result = response.json()
                    voiceprint_id = result.get('voiceprintId')
                    profile.voiceprint_id = voiceprint_id
                    profile.save()
                    messages.success(request, f'Voiceprint created! ID: {voiceprint_id}')
                else:
                    error = response.json().get('error', 'Unknown error')
                    messages.error(request, f'Picovoice error: {error}')
            except Exception as e:
                messages.error(request, f'Voiceprint upload failed: {e}')
        elif voiceprints_saved > 0:
            messages.warning(request, 'Voiceprint saved locally, but not sent to Picovoice (missing key or samples).')

        # Final message
        msg = f'User {username} enrolled.'
        if voiceprint_id:
            msg += ' Voiceprint ready.'
        messages.success(request, msg)
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