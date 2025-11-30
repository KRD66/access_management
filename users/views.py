# users/views.py — FINAL PROFESSIONAL VERSION
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.conf import settings
from .models import UserProfile
import requests
import base64
import os
from datetime import datetime


# ADMIN PASSWORD LOGIN
def admin_login(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            auth_login(request, user)
            return redirect("access_logs:dashboard")
        else:
            messages.error(request, "Invalid admin credentials")
    return render(request, "users/admin_login.html")


# USER VOICE ENTRY GATE
def entry_gate(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("access_logs:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        voice_data = request.POST.get("voice_data")

        if not username or not voice_data:
            messages.error(request, "Please enter username and speak")
            return render(request, "users/entry.html")

        try:
            user = User.objects.get(username__iexact=username)
            profile = user.userprofile

            if user.is_staff:
                messages.error(request, "Admins use password login")
                return render(request, "users/entry.html")

            if not profile.eagle_speaker_id:
                messages.error(request, "Not enrolled")
                return render(request, "users/entry.html")

            # Save & verify voice
            _, b64 = voice_data.split(";base64,")
            audio = base64.b64decode(b64)
            path = "/tmp/entry_voice.webm"
            with open(path, "wb") as f:
                f.write(audio)

            resp = requests.post(
                "https://api.picovoice.ai/eagle/v1/verify",
                headers={"Authorization": f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
                data={"speakerId": profile.eagle_speaker_id},
                files={"audioFile": open(path, "rb")}
            )
            os.remove(path)

            if resp.status_code == 200 and resp.json().get("verified"):
                # Log success
                from access_logs.models import AccessLog
                AccessLog.objects.create(
                    user=user,
                    method="Voice",
                    result="Success",
                    notes=f"Voice command: {profile.voice_phrase}"
                )
                return render(request, "users/access_granted.html", {
                    "user": user,
                    "time": datetime.now().strftime("%I:%M %p")
                })
            else:
                from access_logs.models import AccessLog
                AccessLog.objects.create(
                    user=user,
                    method="Voice",
                    result="Failed",
                    notes="Voice not recognized"
                )
                messages.error(request, "ACCESS DENIED — Voice not recognized")

        except User.DoesNotExist:
            messages.error(request, "User not found")

        return render(request, "users/entry.html")

    return render(request, "users/entry.html")


# ENROLLMENT — ONLY FOR ADMINS
@login_required
def enroll_user(request):
    if not request.user.is_staff:
        messages.error(request, "Access denied")
        return redirect("access_logs:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        phrase = request.POST.get("voice_phrase", "").strip()
        make_admin = request.POST.get("make_admin") == "on"
        voice1 = request.POST.get("voiceprint1")
        voice2 = request.POST.get("voiceprint2")

        if not all([username, phrase, voice1, voice2]):
            messages.error(request, "All fields required")
            return redirect("enroll_user")

        # Create user
        user, created = User.objects.get_or_create(username=username)
        if make_admin:
            user.set_password("admin123")  # default admin pass
            user.is_staff = user.is_superuser = True
        else:
            user.set_unusable_password()
            user.is_staff = user.is_superuser = False
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.voice_phrase = phrase
        profile.role = "admin" if make_admin else "user"

        # Save 2 recordings
        samples = []
        for i, data in enumerate([voice1, voice2], 1):
            _, b64 = data.split(";base64,")
            audio = base64.b64decode(b64)
            path = f"/tmp/enroll_{i}.webm"
            with open(path, "wb") as f:
                f.write(audio)
            samples.append(path)

        files = {"audioFile1": open(samples[0], "rb"), "audioFile2": open(samples[1], "rb")}
        resp = requests.post(
            "https://api.picovoice.ai/eagle/v1/enroll",
            headers={"Authorization": f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
            files=files
        )
        for f in files.values(): f.close()
        for p in samples: os.remove(p)

        if resp.status_code == 200:
            profile.eagle_speaker_id = resp.json()["speakerId"]
            profile.save()
            messages.success(request, f"User '{username}' enrolled successfully!")
        else:
            messages.error(request, "Voice enrollment failed")

        return redirect("enroll_user")

    return render(request, "users/enroll.html")