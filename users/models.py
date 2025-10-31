from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    fingerprint_id = models.CharField(max_length=100, blank=True, null=True)
    voice_phrase = models.CharField(max_length=200, blank=True, null=True) 
    role = models.CharField(max_length=50, choices=[('admin', 'Admin'), ('user', 'User')], default='user')
    created_at = models.DateTimeField(auto_now_add=True)
    voiceprint_file = models.FileField(upload_to='voiceprints/', blank=True, null=True) 

    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
    
