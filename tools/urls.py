from django.urls import path
from . import views

app_name = 'tools'

urlpatterns = [
    # ===== LISTE ET GESTION DES OUTILS =====
    path('', views.tool_list, name='tool_list'),
    path('add/', views.add_tool, name='add_tool'),
    path('<int:tool_id>/edit/', views.edit_tool, name='edit_tool'),
    path('<int:tool_id>/delete/', views.delete_tool, name='delete_tool'),
    path('<int:tool_id>/history/', views.tool_history, name='tool_history'),
    
    # ===== UPLOAD ET SUPPRESSION DES FICHIERS PDF =====
    path('<int:tool_id>/upload-tracability/<str:file_type>/', views.upload_tracability_file, name='upload_tracability'),
    path('<int:tool_id>/delete-tracability/<str:file_type>/', views.delete_tracability_file, name='delete_tracability'),
    
    # ===== ALERTES =====
    path('check-alerts/', views.check_alerts, name='check_alerts'),
    
    # ===== IMPORTS =====
    path('import/', views.import_tools, name='import_tools'),
    path('import/template-excel/', views.download_template_excel, name='download_template_excel'),
    path('import/template-csv/', views.download_template_csv, name='download_template_csv'),
    
    # ===== EXPORTS =====
    path('export/pdf/', views.export_tools_pdf, name='export_tools_pdf'),
    path('export/excel/', views.export_tools_excel, name='export_tools_excel'),
    path('export/alerts-pdf/', views.export_alerts_pdf, name='export_alerts_pdf'),
]