# users/views.py — FINAL SIMPLE & WORKING
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.models import User
from django.conf import settings
from .models import UserProfile
import requests
import base64
import os

def voice_login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        voice_data = request.POST.get("voice_data")

        if not username or not voice_data:
            messages.error(request, "Enter username and record voice")
            return render(request, "login.html")

        try:
            user = User.objects.get(username__iexact=username)
            profile = user.userprofile

            if not profile.eagle_speaker_id:
                messages.error(request, "No voiceprint enrolled. Go to /users/enroll/ first.")
                return render(request, "login.html")

            # Save voice temporarily
            _, b64 = voice_data.split(";base64,")
            audio = base64.b64decode(b64)
            path = "/tmp/temp_voice.webm"
            with open(path, "wb") as f:
                f.write(audio)

            # PICOVOICE CLOUD VERIFY (WORKS!)
            resp = requests.post(
                "https://api.picovoice.ai/eagle/v1/verify",
                headers={"Authorization": f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
                data={"speakerId": profile.eagle_speaker_id},
                files={"audioFile": open(path, "rb")}
            )
            os.remove(path)

            if resp.status_code == 200 and resp.json().get("verified"):
                login(request, user)
                return redirect("access_logs:dashboard")
            else:
                messages.error(request, "Voice not recognized. Try again.")

        except User.DoesNotExist:
            messages.error(request, "User not found")
        except Exception as e:
            messages.error(request, "Login failed")

        return render(request, "login.html")

    return render(request, "login.html")


def enroll_user(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        phrase = request.POST.get("voice_phrase", "").strip()

        if not username or not phrase:
            messages.error(request, "Fill all fields")
            return redirect("enroll_user")

        # Create user
        user, _ = User.objects.get_or_create(username=username)
        user.set_unusable_password()
        user.is_staff = True
        user.is_superuser = True
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.voice_phrase = phrase
        profile.role = "admin"

        # Save 3 voice samples
        samples = []
        for i in range(1, 4):
            data = request.POST.get(f"voiceprint{i}")
            if data:
                _, b64 = data.split(";base64,")
                audio = base64.b64decode(b64)
                path = f"/tmp/enroll_{i}.webm"
                with open(path, "wb") as f:
                    f.write(audio)
                samples.append(path)

        if len(samples) < 3:
            messages.error(request, "Record voice 3 times!")
            return redirect("enroll_user")

        # PICOVOICE CLOUD ENROLL (WORKS!)
        files = {f"audioFile{i}": open(p, "rb") for i, p in enumerate(samples, 1)}
        resp = requests.post(
            "https://api.picovoice.ai/eagle/v1/enroll",
            headers={"Authorization": f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
            files=files
        )
        for f in files.values():
            f.close()
        for p in samples:
            os.remove(p)

        if resp.status_code == 200:
            speaker_id = resp.json()["speakerId"]
            profile.eagle_speaker_id = speaker_id
            profile.save()
            messages.success(request, f"ADMIN {username.upper()} ENROLLED! You can now login with voice only.")
        else:
            messages.error(request, "Enrollment failed. Try again.")

        return redirect("enroll_user")

    return render(request, "users/enroll.html")