from django.contrib import admin
from .models import Calibration

@admin.register(Calibration)
class CalibrationAdmin(admin.ModelAdmin):
    list_display = ['tool', 'calibration_date', 'next_calibration_date', 'performed_by', 'result', 'certificate_number']
    list_filter = ['result', 'calibration_date']
    search_fields = ['tool__name', 'tool__serial_number', 'certificate_number']
    date_hierarchy = 'calibration_date'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('tool', 'calibration_date', 'next_calibration_date')
        }),
        ('Détails', {
            'fields': ('performed_by', 'result', 'certificate_number', 'notes')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )