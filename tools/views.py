from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Tool, ToolHistory
from calibrations.models import Calibration
from datetime import date, timedelta
import json

@login_required
def tool_list(request):
    """Liste des outils avec recherche et filtres"""
    
    # Récupérer tous les outils
    tools = Tool.objects.all().order_by('name')
    
    # Recherche
    search = request.GET.get('search', '')
    if search:
        tools = tools.filter(
            Q(name__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(description__icontains=search) |
            Q(manufacturer__icontains=search) |
            Q(location__icontains=search)
        )
    
    # Filtres
    status_filter = request.GET.get('status', '')
    if status_filter:
        tools = tools.filter(status=status_filter)
    
    alert_filter = request.GET.get('alert', '')
    if alert_filter:
        today = date.today()
        if alert_filter == 'red':
            tools = tools.filter(
                Q(next_calibration_date__lte=today + timedelta(days=7)) &
                Q(next_calibration_date__gte=today) &
                Q(status__in=['active', 'down'])
            )
        elif alert_filter == 'yellow':
            tools = tools.filter(
                Q(next_calibration_date__gt=today + timedelta(days=7)) &
                Q(next_calibration_date__lte=today + timedelta(days=30)) &
                Q(status__in=['active', 'down'])
            )
        elif alert_filter == 'green':
            tools = tools.filter(
                Q(next_calibration_date__gt=today + timedelta(days=30)) &
                Q(next_calibration_date__lte=today + timedelta(days=60)) &
                Q(status__in=['active', 'down'])
            )
        elif alert_filter == 'overdue':
            tools = tools.filter(
                next_calibration_date__lt=today,
                status__in=['active', 'down']
            )
    
    # Pagination (10 par page)
    paginator = Paginator(tools, 10)
    page_number = request.GET.get('page', 1)
    tools_page = paginator.get_page(page_number)
    
    # Statistiques pour les filtres
    total_tools = Tool.objects.count()
    active_tools = Tool.objects.filter(status='active').count()
    under_calibration = Tool.objects.filter(status='under_calibration').count()
    lost_tools = Tool.objects.filter(status='lost').count()
    down_tools = Tool.objects.filter(status='down').count()
    
    context = {
        'tools': tools_page,
        'search': search,
        'status_filter': status_filter,
        'alert_filter': alert_filter,
        'total_tools': total_tools,
        'active_tools': active_tools,
        'under_calibration': under_calibration,
        'lost_tools': lost_tools,
        'down_tools': down_tools,
    }
    
    return render(request, 'tools/tool_list.html', context)


@login_required
def tool_history(request, tool_id):
    """Récupère l'historique d'un outil (pour le double-clic)"""
    
    tool = get_object_or_404(Tool, id=tool_id)
    
    # Récupérer les calibrations
    calibrations = Calibration.objects.filter(tool=tool).order_by('-calibration_date')
    
    # Récupérer l'audit log
    history = ToolHistory.objects.filter(tool=tool).order_by('-created_at')
    
    # Merger les deux historiques
    timeline = []
    
    for cal in calibrations:
        timeline.append({
            'type': 'calibration',
            'date': cal.calibration_date,
            'result': cal.result,
            'technician': str(cal.technician) if cal.technician else 'N/A',
            'next_date': cal.next_calibration_date,
            'notes': cal.notes,
        })
    
    for log in history:
        timeline.append({
            'type': log.action,
            'date': log.created_at,
            'user': str(log.user) if log.user else 'Système',
            'field': log.field_name,
            'old_value': log.old_value,
            'new_value': log.new_value,
            'description': log.description,
        })
    
    # Trier par date (plus récent d'abord)
    timeline.sort(key=lambda x: x['date'], reverse=True)
    
    data = {
        'tool': {
            'id': tool.id,
            'name': tool.name,
            'serial_number': tool.serial_number,
            'status': tool.status,
            'location': tool.location,
            'next_calibration': tool.next_calibration_date.strftime('%d/%m/%Y'),
        },
        'stats': {
            'total_calibrations': calibrations.count(),
            'last_calibration': calibrations.first().calibration_date.strftime('%d/%m/%Y') if calibrations.exists() else 'Aucune',
        },
        'timeline': timeline,
    }
    
    return render(request, 'tools/tool_history_modal.html', {'data': data})


@login_required
def add_tool(request):
    """Ajouter un nouvel outil"""
    
    if request.method == 'POST':
        # Récupérer les données du formulaire
        name = request.POST.get('name')
        serial_number = request.POST.get('serial_number')
        description = request.POST.get('description', '')
        manufacturer = request.POST.get('manufacturer', '')
        tool_type = request.POST.get('tool_type', '')
        location = request.POST.get('location', '')
        next_calibration_date = request.POST.get('next_calibration_date')
        calibration_frequency_months = request.POST.get('calibration_frequency_months', 6)
        status = request.POST.get('status', 'active')
        
        # Validation basique
        if not name or not serial_number:
            messages.error(request, "Le nom et le numéro de série sont obligatoires")
            return render(request, 'tools/add_tool.html')
        
        # Créer l'outil
        from datetime import datetime
        tool = Tool.objects.create(
            name=name,
            serial_number=serial_number,
            description=description,
            manufacturer=manufacturer,
            tool_type=tool_type,
            location=location,
            next_calibration_date=datetime.strptime(next_calibration_date, '%Y-%m-%d').date() if next_calibration_date else None,
            calibration_frequency_months=int(calibration_frequency_months),
            status=status,
            created_by=request.user
        )
        
        messages.success(request, f"L'outil {name} a été créé avec succès !")
        return redirect('tools:tool_list')
    
    return render(request, 'tools/add_tool.html')


@login_required
def check_alerts(request):
    """Vérifier les alertes manuellement"""
    from django.core.management import call_command
    from io import StringIO
    
    out = StringIO()
    try:
        call_command('check_calibrations', stdout=out)
        messages.success(request, "✅ Alertes vérifiées avec succès !")
    except Exception as e:
        messages.error(request, f"❌ Erreur lors de la vérification : {str(e)}")
    
    return redirect('dashboard:dashboard')


@login_required
def edit_tool(request, tool_id):
    """Modifier un outil existant"""
    tool = get_object_or_404(Tool, id=tool_id)
    
    if request.method == 'POST':
        # Récupérer les données du formulaire
        name = request.POST.get('name')
        serial_number = request.POST.get('serial_number')
        description = request.POST.get('description', '')
        manufacturer = request.POST.get('manufacturer', '')
        tool_type = request.POST.get('tool_type', '')
        location = request.POST.get('location', '')
        next_calibration_date = request.POST.get('next_calibration_date')
        calibration_frequency_months = request.POST.get('calibration_frequency_months', 6)
        status = request.POST.get('status', 'active')
        
        # Validation
        if not name or not serial_number:
            messages.error(request, "Le nom et le numéro de série sont obligatoires")
            return render(request, 'tools/edit_tool.html', {'tool': tool})
        
        # Mettre à jour
        from datetime import datetime
        tool.name = name
        tool.serial_number = serial_number
        tool.description = description
        tool.manufacturer = manufacturer
        tool.tool_type = tool_type
        tool.location = location
        if next_calibration_date:
            tool.next_calibration_date = datetime.strptime(next_calibration_date, '%Y-%m-%d').date()
        tool.calibration_frequency_months = int(calibration_frequency_months)
        tool.status = status
        tool.save()
        
        # Historique
        ToolHistory.objects.create(
            tool=tool,
            user=request.user,
            action='updated',
            description=f"Outil modifié par {request.user.username}",
            field_name='multiple',
            old_value='',
            new_value=''
        )
        
        messages.success(request, f"✅ L'outil {name} a été modifié avec succès !")
        return redirect('tools:tool_list')
    
    return render(request, 'tools/edit_tool.html', {'tool': tool})


@login_required
def delete_tool(request, tool_id):
    """Supprimer un outil (réservé aux Supervisors)"""
    tool = get_object_or_404(Tool, id=tool_id)
    
    # Vérification des droits
    if not request.user.is_superuser:
        messages.error(request, "❌ Seul un Superviseur peut supprimer des outils")
        return redirect('tools:tool_list')
    
    if request.method == 'POST':
        tool_name = tool.name
        tool.delete()
        messages.success(request, f"🗑️ L'outil {tool_name} a été supprimé avec succès !")
        return redirect('tools:tool_list')
    
    return render(request, 'tools/delete_tool.html', {'tool': tool})