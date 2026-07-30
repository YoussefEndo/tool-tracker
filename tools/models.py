from django.db import models
from django.contrib.auth.models import User
from datetime import date

class Tool(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('under_calibration', 'Under Calibration'),
        ('lost', 'Lost'),
        ('down', 'Down'),
    ]
    
    ALERT_CHOICES = [
        ('none', 'Aucune'),
        ('green', 'Vert'),
        ('yellow', 'Jaune'),
        ('red', 'Rouge'),
    ]

    # Informations principales
    name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    calibration_frequency_months = models.PositiveIntegerField(default=6)
    next_calibration_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    alert_level = models.CharField(max_length=10, choices=ALERT_CHOICES, default='none')  # NOUVEAU
    location = models.CharField(max_length=200, blank=True)

    # Données Excel
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    tool_type = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    first_calibration_date = models.DateField(blank=True, null=True)
    status_reception = models.CharField(max_length=100, blank=True, null=True)
    validation_status = models.CharField(max_length=100, blank=True, null=True)  # AJOUTÉ
    gpn = models.CharField(max_length=100, blank=True, null=True)
    internal_number = models.CharField(max_length=100, blank=True, null=True)
    comments = models.TextField(blank=True, null=True)  # AJOUTÉ

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='tools_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

    @property
    def alert_status(self):
        """Calcule le niveau d'alerte basé sur la date du prochain étalonnage"""
        today = date.today()
        delta = (self.next_calibration_date - today).days

        if delta < 0:
            return 'overdue'
        elif delta <= 7:
            return 'red'
        elif delta <= 30:
            return 'yellow'
        elif delta <= 60:
            return 'green'
        else:
            return 'none'

    def update_alert_level(self):
        """Met à jour le champ alert_level basé sur alert_status"""
        self.alert_level = self.alert_status
        self.save(update_fields=['alert_level'])


class ToolHistory(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('calibrated', 'Calibrated'),
        ('status_changed', 'Status Changed'),
        ('deleted', 'Deleted'),  # AJOUTÉ
    ]

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='history')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    field_name = models.CharField(max_length=100, blank=True, null=True)  # AJOUTÉ
    old_value = models.TextField(blank=True, null=True)  # AJOUTÉ
    new_value = models.TextField(blank=True, null=True)  # AJOUTÉ
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} on {self.tool.name} by {self.user}"