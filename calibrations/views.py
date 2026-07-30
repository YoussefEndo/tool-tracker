from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from tools.models import Tool, ToolHistory
from .models import Calibration
from datetime import date, timedelta

@login_required
def add_calibration(request, tool_id):
    """Ajouter une calibration pour un outil"""
    tool = get_object_or_404(Tool, id=tool_id)
    
    if request.method == 'POST':
        calibration_date = request.POST.get('calibration_date')
        next_calibration_date = request.POST.get('next_calibration_date')
        performed_by = request.POST.get('performed_by')
        result = request.POST.get('result')
        notes = request.POST.get('notes', '')
        certificate_number = request.POST.get('certificate_number', '')
        
        # Validation
        if not calibration_date or not next_calibration_date or not performed_by or not result:
            messages.error(request, "Tous les champs obligatoires doivent être remplis")
            return render(request, 'calibrations/add_calibration.html', {'tool': tool})
        
        # Créer la calibration
        calibration = Calibration.objects.create(
            tool=tool,
            calibration_date=calibration_date,
            next_calibration_date=next_calibration_date,
            performed_by=performed_by,
            result=result,
            notes=notes,
            certificate_number=certificate_number,
            created_by=request.user
        )
        
        # Mettre à jour l'outil
        tool.next_calibration_date = next_calibration_date
        if result == 'pass':
            tool.status = 'active'
        else:
            tool.status = 'down'
        tool.save()
        
        # Créer l'historique
        ToolHistory.objects.create(
            tool=tool,
            user=request.user,
            action='calibrated',
            description=f"Calibration enregistrée: {result}",
            field_name='calibration',
            old_value='',
            new_value=calibration_date
        )
        
        messages.success(request, f"Calibration enregistrée pour {tool.name}")
        return redirect('tools:tool_list')
    
    return render(request, 'calibrations/add_calibration.html', {'tool': tool})