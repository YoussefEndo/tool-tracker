from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q  # <- Import unique de Q
from tools.models import Tool
from datetime import date, timedelta

@login_required
def dashboard(request):
    """Vue principale du tableau de bord"""
    
    today = date.today()
    two_months_later = today + timedelta(days=60)
    
    # 1. Tools to calibrate (étalonnage dans les 2 mois)
    tools_to_calibrate = Tool.objects.filter(
        Q(next_calibration_date__lte=two_months_later) &
        Q(status__in=['active', 'down'])
    ).count()
    
    # 2. Under Calibration
    under_calibration = Tool.objects.filter(
        status='under_calibration'
    ).count()
    
    # 3. Lost Tools
    lost_tools = Tool.objects.filter(
        status='lost'
    ).count()
    
    # 4. Down Tools
    down_tools = Tool.objects.filter(
        status='down'
    ).count()
    
    # Stats supplémentaires
    total_tools = Tool.objects.exclude(
        status='lost'
    ).count()
    
    # Alertes par niveau
    red_alerts = Tool.objects.filter(
        Q(next_calibration_date__lte=today + timedelta(days=7)) &
        Q(next_calibration_date__gte=today) &
        Q(status__in=['active', 'down'])
    ).count()
    
    overdue = Tool.objects.filter(
        next_calibration_date__lt=today,
        status__in=['active', 'down']
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
    
    # Récupérer les outils en alerte (pour la liste)
    alert_tools = Tool.objects.filter(
        Q(next_calibration_date__lte=two_months_later) &
        Q(status__in=['active', 'down'])
    ).order_by('next_calibration_date')[:10]
    
    context = {
        'tools_to_calibrate': tools_to_calibrate,
        'under_calibration': under_calibration,
        'lost_tools': lost_tools,
        'down_tools': down_tools,
        'total_tools': total_tools,
        'red_alerts': red_alerts,
        'yellow_alerts': yellow_alerts,
        'green_alerts': green_alerts,
        'overdue': overdue,
        'alert_tools': alert_tools,
    }
    
    return render(request, 'dashboard/dashboard.html', context)