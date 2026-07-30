from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.user_list, name='user_list'),
    path('create/', views.user_create, name='user_create'),
    path('<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('<int:user_id>/delete/', views.user_delete, name='user_delete'),
    path('<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
]