from django.db import models
from users.models import UserProfile

class AccessLog(models.Model):
    RESULT_CHOICES = [('success', 'Success'), ('failure', 'Failure')]
    METHOD_CHOICES = [('fingerprint', 'Fingerprint'), ('voice', 'Voice')]

    user_profile = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True)
    device = models.CharField(max_length=100)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.method} - {self.result} at {self.timestamp}"