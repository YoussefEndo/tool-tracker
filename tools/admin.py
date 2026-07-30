from django.contrib import admin
from .models import Tool, ToolHistory

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ['name', 'serial_number', 'tool_type', 'manufacturer', 'status', 'next_calibration_date', 'location']
    list_filter = ['status', 'tool_type', 'manufacturer']
    search_fields = ['name', 'serial_number', 'description', 'manufacturer']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('name', 'serial_number', 'description', 'tool_type', 'manufacturer')
        }),
        ('Dates', {
            'fields': ('purchase_date', 'first_calibration_date', 'next_calibration_date', 'calibration_frequency_months')
        }),
        ('Statut et localisation', {
            'fields': ('status', 'location', 'department')
        }),
        ('Données Excel', {
            'fields': ('gpn', 'internal_number', 'status_reception', 'validation_status', 'comments'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ToolHistory)
class ToolHistoryAdmin(admin.ModelAdmin):
    list_display = ['tool', 'action', 'user', 'created_at']
    list_filter = ['action', 'created_at']