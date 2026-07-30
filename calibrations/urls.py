from django.urls import path
from . import views

app_name = 'calibrations'

urlpatterns = [
    path('add/<int:tool_id>/', views.add_calibration, name='add_calibration'),
]