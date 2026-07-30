from django.db import models
from django.contrib.auth.models import User
from tools.models import Tool

class Calibration(models.Model):
    RESULT_CHOICES = [
        ('pass', 'Pass'),
        ('fail', 'Fail'),
    ]

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='calibrations')
    calibration_date = models.DateField()
    next_calibration_date = models.DateField()
    performed_by = models.CharField(max_length=200)
    certificate_number = models.CharField(max_length=100, blank=True)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='calibrations_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-calibration_date']

    def __str__(self):
        return f"Calibration {self.tool.name} - {self.calibration_date}"