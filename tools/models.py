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

    # ===== COLONNES EXCEL =====
    lp = models.IntegerField(null=True, blank=True)
    internal_number = models.CharField(max_length=100, blank=True, null=True)
    gpn = models.CharField(max_length=100, blank=True, null=True)
    tool_type = models.CharField(max_length=100, blank=True, null=True)
    tool_index = models.CharField(max_length=50, blank=True, null=True)
    number = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=500, blank=True, null=True)
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    tool_description = models.TextField(blank=True, null=True)
    connector_number = models.CharField(max_length=100, blank=True, null=True)
    first_calibration = models.DateField(blank=True, null=True)
    next_calibration_date = models.DateField()
    department = models.CharField(max_length=200, blank=True, null=True)
    calibration_tracability = models.TextField(blank=True, null=True)
    reception_tracability = models.TextField(blank=True, null=True)
    name_surname = models.CharField(max_length=200, blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    order_no = models.CharField(max_length=100, blank=True, null=True)
    status_reception = models.CharField(max_length=100, blank=True, null=True)
    validation_status = models.CharField(max_length=100, blank=True, null=True)
    
    # ===== CHAMPS SYSTÈME =====
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    alert_level = models.CharField(max_length=10, choices=ALERT_CHOICES, default='none')
    calibration_frequency_months = models.PositiveIntegerField(default=6)
    
    # ===== NOUVEAUX CHAMPS POUR LES FICHIERS PDF =====
    calibration_pdf = models.FileField(upload_to='calibration_pdfs/%Y/%m/', blank=True, null=True)
    reception_pdf = models.FileField(upload_to='reception_pdfs/%Y/%m/', blank=True, null=True)
    calibration_pdf_uploaded_at = models.DateTimeField(blank=True, null=True)
    reception_pdf_uploaded_at = models.DateTimeField(blank=True, null=True)
    calibration_pdf_uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='calibration_pdf_uploads'
    )
    reception_pdf_uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reception_pdf_uploads'
    )
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='tools_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.description} ({self.number})"

    @property
    def alert_status(self):
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
        self.alert_level = self.alert_status
        self.save(update_fields=['alert_level'])


class ToolHistory(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('calibrated', 'Calibrated'),
        ('status_changed', 'Status Changed'),
        ('deleted', 'Deleted'),
        ('calibration_tracability_uploaded', 'Calibration Tracability Uploaded'),
        ('reception_tracability_uploaded', 'Reception Tracability Uploaded'),
        ('calibration_tracability_deleted', 'Calibration Tracability Deleted'),
        ('reception_tracability_deleted', 'Reception Tracability Deleted'),
    ]

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='history')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    field_name = models.CharField(max_length=100, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    description = models.TextField()
    
    # ===== NOUVEAUX CHAMPS POUR LES FICHIERS =====
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_url = models.CharField(max_length=500, blank=True, null=True)
    
    # ===== CHAMPS POUR LE SUIVI =====
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tool', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        user_name = self.user.username if self.user else 'Système'
        return f"{self.get_action_display()} - {self.tool.description} par {user_name}"

    @classmethod
    def log_action(cls, tool, user, action, description, field_name=None, old_value=None, new_value=None, file_name=None, file_url=None, request=None):
        """Méthode utilitaire pour créer un log facilement"""
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return cls.objects.create(
            tool=tool,
            user=user,
            action=action,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            description=description,
            file_name=file_name,
            file_url=file_url,
            ip_address=ip_address,
            user_agent=user_agent
        )