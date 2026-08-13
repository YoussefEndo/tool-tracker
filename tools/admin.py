from django.contrib import admin
from .models import Tool, ToolHistory

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'description',          # Nom de l'outil (ex: "Cutter 726620/125H - Perschmann")
        'number',               # Numéro (ex: "45-1")
        'manufacturer',         # Fabricant (ex: "HOFFMANN")
        'tool_type',            # Type (ex: "standard hand tool")
        'status',
        'next_calibration_date',
        'alert_level',
        'location'
    ]
    list_filter = ['status', 'tool_type', 'manufacturer', 'alert_level']
    search_fields = [
        'number',
        'description',
        'manufacturer',
        'tool_type',
        'location',
        'internal_number',
        'gpn'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('📋 Informations Excel', {
            'fields': (
                'lp',
                'internal_number',
                'gpn',
                'tool_type',
                'tool_index',
                'number',
                'description',
                'manufacturer',
                'tool_description',
                'connector_number',
                'department',
                'calibration_tracability',
                'reception_tracability',
                'name_surname',
                'location',
                'comments',
                'order_no',
                'status_reception',
                'validation_status'
            )
        }),
        ('📅 Calibration', {
            'fields': (
                'first_calibration',
                'next_calibration_date',
                'calibration_frequency_months',
                'status',
                'alert_level'
            )
        }),
        ('👤 Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ToolHistory)
class ToolHistoryAdmin(admin.ModelAdmin):
    list_display = ['tool', 'action', 'user', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['tool__number', 'tool__description', 'description']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Historique', {
            'fields': ('tool', 'user', 'action', 'description')
        }),
        ('Détails', {
            'fields': ('field_name', 'old_value', 'new_value')
        }),
        ('Date', {
            'fields': ('created_at',)
        }),
    )