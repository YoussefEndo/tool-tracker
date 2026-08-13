from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from tools.models import Tool
from datetime import date, timedelta

@login_required
def dashboard(request):
    """Vue principale du tableau de bord avec graphiques"""
    
    today = date.today()
    two_months_later = today + timedelta(days=60)
    
    # ===== STATISTIQUES PRINCIPALES =====
    
    tools_to_calibrate = Tool.objects.filter(
        Q(next_calibration_date__lte=two_months_later) &
        Q(status__in=['active', 'down'])
    ).count()
    
    under_calibration = Tool.objects.filter(
        status='under_calibration'
    ).count()
    
    lost_tools = Tool.objects.filter(
        status='lost'
    ).count()
    
    down_tools = Tool.objects.filter(
        status='down'
    ).count()
    
    # ===== STATS SUPPLÉMENTAIRES =====
    
    total_tools = Tool.objects.exclude(
        status='lost'
    ).count()
    
    active_tools = Tool.objects.filter(status='active').count()
    
    # ===== ALERTES PAR NIVEAU =====
    
    overdue = Tool.objects.filter(
        next_calibration_date__lt=today,
        status__in=['active', 'down']
    ).count()
    
    red_alerts = Tool.objects.filter(
        Q(next_calibration_date__lte=today + timedelta(days=7)) &
        Q(next_calibration_date__gte=today) &
        Q(status__in=['active', 'down'])
    ).count()
    
    yellow_alerts = Tool.objects.filter(
        Q(next_calibration_date__gt=today + timedelta(days=7)) &
        Q(next_calibration_date__lte=today + timedelta(days=30)) &
        Q(status__in=['active', 'down'])
    ).count()
    
    green_alerts = Tool.objects.filter(
        Q(next_calibration_date__gt=today + timedelta(days=30)) &
        Q(next_calibration_date__lte=today + timedelta(days=60)) &
        Q(status__in=['active', 'down'])
    ).count()
    
    # ===== LISTE DES ALERTES PRIORITAIRES =====
    
    alert_tools = Tool.objects.filter(
        Q(next_calibration_date__lte=two_months_later) &
        Q(status__in=['active', 'down'])
    ).order_by('next_calibration_date')[:10]
    
    # ===== DONNÉES POUR LES GRAPHIQUES (formatées en listes Python) =====
    
    # Graphique des statuts
    status_stats = Tool.objects.values('status').annotate(count=Count('status'))
    status_labels = []
    status_data = []
    status_colors = []
    
    status_color_map = {
        'active': '#22c55e',
        'under_calibration': '#f59e0b',
        'lost': '#ef4444',
        'down': '#6b7280'
    }
    
    status_label_map = {
        'active': 'Actifs',
        'under_calibration': 'En calibration',
        'lost': 'Perdus',
        'down': 'Hors service'
    }
    
    for stat in status_stats:
        status_labels.append(status_label_map.get(stat['status'], stat['status']))
        status_data.append(stat['count'])
        status_colors.append(status_color_map.get(stat['status'], '#4f46e5'))
    
    # Graphique des alertes
    alert_labels = ['En retard', 'Rouge (≤7j)', 'Jaune (≤30j)', 'Vert (≤60j)']
    alert_data = [overdue, red_alerts, yellow_alerts, green_alerts]
    alert_colors = ['#dc2626', '#dc2626', '#f59e0b', '#22c55e']
    
    # ===== CONTEXTE =====
    
    context = {
        # Stats principales
        'tools_to_calibrate': tools_to_calibrate,
        'under_calibration': under_calibration,
        'lost_tools': lost_tools,
        'down_tools': down_tools,
        'total_tools': total_tools,
        'active_tools': active_tools,
        
        # Alertes
        'red_alerts': red_alerts,
        'yellow_alerts': yellow_alerts,
        'green_alerts': green_alerts,
        'overdue': overdue,
        'alert_tools': alert_tools,
        
        # Données pour les graphiques (comme listes Python)
        'status_labels': status_labels,
        'status_data': status_data,
        'status_colors': status_colors,
        'alert_labels': alert_labels,
        'alert_data': alert_data,
        'alert_colors': alert_colors,
    }
    
    return render(request, 'dashboard/dashboard.html', context)