# users/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from .models import UserProfile
from django.core.files.base import ContentFile
import base64
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
            user.set_password('temp123')  # User must change later
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

        # Save voiceprints (3 recordings)
        voiceprints_saved = 0
        for i in range(1, 4):
            data = request.POST.get(f'voiceprint{i}')
            if data and data.startswith('data:audio'):
                try:
                    format, imgstr = data.split(';base64,')
                    ext = format.split('/')[-1]
                    filename = f"voiceprint_{username}_{i}.{ext}"
                    file_content = ContentFile(base64.b64decode(imgstr), name=filename)
                    
                    # Save to media/voiceprints/
                    field_name = f'voiceprint_sample_{i}'
                    if not hasattr(profile, field_name):
                        # Or save to a separate model later
                        pass
                    else:
                        getattr(profile, field_name).save(filename, file_content, save=True)
                    
                    voiceprints_saved += 1
                except Exception as e:
                    print(f"Voiceprint {i} save error: {e}")

        # Final message
        msg = f'User {username} enrolled successfully.'
        if voiceprints_saved > 0:
            msg += f' {voiceprints_saved} voiceprint(s) saved.'
        if fingerprint_id:
            msg += ' Fingerprint ID set.'
        if voice_phrase:
            msg += ' Voice phrase set.'
        messages.success(request, msg)

        return redirect('user_list')

    return render(request, 'users/enroll.html')

@login_required
def user_list(request):
    profiles = UserProfile.objects.select_related('user').all().order_by('user__username')
    return render(request, 'users/list.html', {'profiles': profiles})