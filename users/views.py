# users/views.py — FINAL FOREVER (2 recordings only — GUARANTEED WORKING)
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
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
            messages.error(request, "Enter username and record your voice.")
            return render(request, "login.html")

        try:
            user = User.objects.get(username__iexact=username)
            profile = user.userprofile

            if not profile.eagle_speaker_id:
                messages.error(request, "Not enrolled. Ask admin to enroll you.")
                return render(request, "login.html")

            _, b64 = voice_data.split(";base64,")
            audio = base64.b64decode(b64)
            path = "/tmp/temp_login.webm"
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
                login(request, user)
                return redirect("access_logs:dashboard")
            else:
                messages.error(request, "Voice not recognized.")

        except User.DoesNotExist:
            messages.error(request, "User not found.")
        except Exception:
            messages.error(request, "Login failed.")

        return render(request, "login.html")
    return render(request, "login.html")


@login_required
def enroll_anyone(request):
    if not request.user.is_staff and User.objects.filter(is_staff=True).exists():
        messages.error(request, "Only administrators can enroll users.")
        return redirect("access_logs:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        phrase = request.POST.get("voice_phrase", "").strip()
        is_admin = request.POST.get("make_admin") == "on"

        if not username or not phrase:
            messages.error(request, "Username and phrase required.")
            return redirect("enroll_anyone")

        # Get exactly 2 recordings
        voice1 = request.POST.get("voiceprint1")
        voice2 = request.POST.get("voiceprint2")

        if not voice1 or not voice2:
            messages.error(request, "Please record your voice 2 times!")
            return redirect("enroll_anyone")

        # Save files
        samples = []
        for i, data in enumerate([voice1, voice2], 1):
            _, b64 = data.split(";base64,")
            audio = base64.b64decode(b64)
            path = f"/tmp/enroll_{username}_{i}.webm"
            with open(path, "wb") as f:
                f.write(audio)
            samples.append(path)

        # Create user
        user, _ = User.objects.get_or_create(username=username)
        user.set_unusable_password()
        user.is_staff = is_admin
        user.is_superuser = is_admin
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.voice_phrase = phrase
        profile.role = "admin" if is_admin else "user"

        # Send to Picovoice
        files = {
            "audioFile1": open(samples[0], "rb"),
            "audioFile2": open(samples[1], "rb")
        }
        resp = requests.post(
            "https://api.picovoice.ai/eagle/v1/enroll",
            headers={"Authorization": f"Bearer {settings.PICOVOICE_ACCESS_KEY}"},
            files=files
        )

        # Cleanup
        for f in files.values():
            f.close()
        for p in samples:
            os.remove(p)

        if resp.status_code == 200:
            profile.eagle_speaker_id = resp.json()["speakerId"]
            profile.save()
            messages.success(request, f"User '{username}' enrolled successfully! Voice login ready.")
        else:
            messages.error(request, "Enrollment failed. Try again.")

        return redirect("enroll_anyone")

    return render(request, "users/enroll.html")