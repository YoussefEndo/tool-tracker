from django.urls import path
from . import views

app_name = 'tools'

urlpatterns = [
    path('', views.tool_list, name='tool_list'),
    path('add/', views.add_tool, name='add_tool'),
    path('check-alerts/', views.check_alerts, name='check_alerts'),
    path('<int:tool_id>/edit/', views.edit_tool, name='edit_tool'),
    path('<int:tool_id>/delete/', views.delete_tool, name='delete_tool'),
    path('<int:tool_id>/history/', views.tool_history, name='tool_history'),
]