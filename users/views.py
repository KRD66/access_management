from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserProfile
from django.contrib.auth.models import User

@login_required
def enroll_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        role = request.POST['role']
        fingerprint_id = request.POST.get('fingerprint_id', '')

        user, created = User.objects.get_or_create(username=username, defaults={'email': email})
        if created:
            user.set_password('default123')
            user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.fingerprint_id = fingerprint_id
        profile.role = role
        profile.save()

        messages.success(request, f'User {username} enrolled!')
        return redirect('user_list')

    return render(request, 'users/enroll.html')

@login_required
def user_list(request):
    profiles = UserProfile.objects.all()
    return render(request, 'users/list.html', {'profiles': profiles})