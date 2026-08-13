from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Tool, ToolHistory
from calibrations.models import Calibration
from datetime import date, timedelta, datetime
import json
import io
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import xlsxwriter
import os
import logging
import pandas as pd
import csv
import chardet

logger = logging.getLogger('tools')

@login_required
def tool_list(request):
    """Liste des outils avec recherche et filtres"""
    
    tools = Tool.objects.all().order_by('description')
    
    search = request.GET.get('search', '')
    if search:
        tools = tools.filter(
            Q(description__icontains=search) |
            Q(number__icontains=search) |
            Q(tool_description__icontains=search) |
            Q(manufacturer__icontains=search) |
            Q(location__icontains=search) |
            Q(internal_number__icontains=search) |
            Q(gpn__icontains=search) |
            Q(tool_type__icontains=search) |
            Q(department__icontains=search)
        )
    
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
    
    paginator = Paginator(tools, 10)
    page_number = request.GET.get('page', 1)
    tools_page = paginator.get_page(page_number)
    
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
    """Récupère l'historique d'un outil avec les fichiers PDF"""
    
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
            'file_name': log.file_name,
            'file_url': log.file_url,
        })
    
    timeline.sort(key=lambda x: x['date'], reverse=True)
    
    # Préparer les données des fichiers PDF
    calibration_pdf = None
    reception_pdf = None
    
    if tool.calibration_pdf:
        calibration_pdf = {
            'name': os.path.basename(tool.calibration_pdf.name),
            'url': tool.calibration_pdf.url,
            'size': tool.calibration_pdf.size,
            'uploaded_at': tool.calibration_pdf_uploaded_at.strftime('%d/%m/%Y %H:%M') if tool.calibration_pdf_uploaded_at else None,
            'uploaded_by': str(tool.calibration_pdf_uploaded_by) if tool.calibration_pdf_uploaded_by else None,
        }
    
    if tool.reception_pdf:
        reception_pdf = {
            'name': os.path.basename(tool.reception_pdf.name),
            'url': tool.reception_pdf.url,
            'size': tool.reception_pdf.size,
            'uploaded_at': tool.reception_pdf_uploaded_at.strftime('%d/%m/%Y %H:%M') if tool.reception_pdf_uploaded_at else None,
            'uploaded_by': str(tool.reception_pdf_uploaded_by) if tool.reception_pdf_uploaded_by else None,
        }
    
    data = {
        'tool': {
            'id': tool.id,
            'name': tool.description,
            'serial_number': tool.number,
            'status': tool.status,
            'location': tool.location,
            'next_calibration': tool.next_calibration_date.strftime('%d/%m/%Y'),
            'validation_status': tool.validation_status,
        },
        'stats': {
            'total_calibrations': calibrations.count(),
            'last_calibration': calibrations.first().calibration_date.strftime('%d/%m/%Y') if calibrations.exists() else 'Aucune',
        },
        'timeline': timeline,
        'files': {
            'calibration': calibration_pdf,
            'reception': reception_pdf,
        }
    }
    
    return render(request, 'tools/tool_history_modal.html', {'data': data})


@login_required
@require_POST
def upload_tracability_file(request, tool_id, file_type):
    """Uploader un fichier de traçabilité (calibration ou reception)"""
    
    tool = get_object_or_404(Tool, id=tool_id)
    
    # Vérifier les permissions (seul Superuser peut uploader)
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Permission refusée. Seul un Superviseur peut uploader des fichiers.'}, status=403)
    
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Aucun fichier fourni'}, status=400)
    
    file = request.FILES['file']
    
    # Vérifier l'extension
    if not file.name.endswith('.pdf'):
        return JsonResponse({'error': 'Le fichier doit être un PDF'}, status=400)
    
    # Vérifier la taille (max 10MB)
    if file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Le fichier ne doit pas dépasser 10MB'}, status=400)
    
    try:
        if file_type == 'calibration':
            # Supprimer l'ancien fichier si existant
            if tool.calibration_pdf:
                default_storage.delete(tool.calibration_pdf.path)
            
            tool.calibration_pdf = file
            tool.calibration_pdf_uploaded_at = datetime.now()
            tool.calibration_pdf_uploaded_by = request.user
            tool.save()
            
            # Log de l'action
            ToolHistory.log_action(
                tool=tool,
                user=request.user,
                action='calibration_tracability_uploaded',
                description=f"Fichier de traçabilité d'étalonnage uploadé par {request.user.username}",
                field_name='calibration_pdf',
                new_value=file.name,
                file_name=file.name,
                file_url=tool.calibration_pdf.url,
                request=request
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Fichier de traçabilité uploadé avec succès',
                'file': {
                    'name': file.name,
                    'url': tool.calibration_pdf.url,
                    'size': file.size,
                    'uploaded_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                    'uploaded_by': str(request.user),
                }
            })
            
        elif file_type == 'reception':
            # Supprimer l'ancien fichier si existant
            if tool.reception_pdf:
                default_storage.delete(tool.reception_pdf.path)
            
            tool.reception_pdf = file
            tool.reception_pdf_uploaded_at = datetime.now()
            tool.reception_pdf_uploaded_by = request.user
            tool.save()
            
            # Log de l'action
            ToolHistory.log_action(
                tool=tool,
                user=request.user,
                action='reception_tracability_uploaded',
                description=f"Fichier de traçabilité de réception uploadé par {request.user.username}",
                field_name='reception_pdf',
                new_value=file.name,
                file_name=file.name,
                file_url=tool.reception_pdf.url,
                request=request
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Fichier de traçabilité uploadé avec succès',
                'file': {
                    'name': file.name,
                    'url': tool.reception_pdf.url,
                    'size': file.size,
                    'uploaded_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                    'uploaded_by': str(request.user),
                }
            })
            
        else:
            return JsonResponse({'error': 'Type de fichier invalide'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def delete_tracability_file(request, tool_id, file_type):
    """Supprimer un fichier de traçabilité"""
    
    tool = get_object_or_404(Tool, id=tool_id)
    
    # Vérifier les permissions
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Permission refusée. Seul un Superviseur peut supprimer des fichiers.'}, status=403)
    
    try:
        if file_type == 'calibration':
            if tool.calibration_pdf:
                file_name = os.path.basename(tool.calibration_pdf.name)
                default_storage.delete(tool.calibration_pdf.path)
                tool.calibration_pdf = None
                tool.calibration_pdf_uploaded_at = None
                tool.calibration_pdf_uploaded_by = None
                tool.save()
                
                ToolHistory.log_action(
                    tool=tool,
                    user=request.user,
                    action='calibration_tracability_deleted',
                    description=f"Fichier de traçabilité d'étalonnage supprimé par {request.user.username}",
                    field_name='calibration_pdf',
                    old_value=file_name,
                    request=request
                )
                
                return JsonResponse({'success': True, 'message': 'Fichier supprimé avec succès'})
            else:
                return JsonResponse({'error': 'Aucun fichier à supprimer'}, status=404)
                
        elif file_type == 'reception':
            if tool.reception_pdf:
                file_name = os.path.basename(tool.reception_pdf.name)
                default_storage.delete(tool.reception_pdf.path)
                tool.reception_pdf = None
                tool.reception_pdf_uploaded_at = None
                tool.reception_pdf_uploaded_by = None
                tool.save()
                
                ToolHistory.log_action(
                    tool=tool,
                    user=request.user,
                    action='reception_tracability_deleted',
                    description=f"Fichier de traçabilité de réception supprimé par {request.user.username}",
                    field_name='reception_pdf',
                    old_value=file_name,
                    request=request
                )
                
                return JsonResponse({'success': True, 'message': 'Fichier supprimé avec succès'})
            else:
                return JsonResponse({'error': 'Aucun fichier à supprimer'}, status=404)
                
        else:
            return JsonResponse({'error': 'Type de fichier invalide'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def add_tool(request):
    """Ajouter un nouvel outil"""
    
    if request.method == 'POST':
        description = request.POST.get('description')
        number = request.POST.get('number')
        tool_description = request.POST.get('tool_description', '')
        manufacturer = request.POST.get('manufacturer', '')
        tool_type = request.POST.get('tool_type', '')
        location = request.POST.get('location', '')
        next_calibration_date = request.POST.get('next_calibration_date')
        calibration_frequency_months = request.POST.get('calibration_frequency_months', 6)
        status = request.POST.get('status', 'active')
        
        if not description or not number:
            messages.error(request, "Le nom et le numéro de série sont obligatoires")
            return render(request, 'tools/add_tool.html')
        
        from datetime import datetime as dt
        tool = Tool.objects.create(
            description=description,
            number=number,
            tool_description=tool_description,
            manufacturer=manufacturer,
            tool_type=tool_type,
            location=location,
            next_calibration_date=dt.strptime(next_calibration_date, '%Y-%m-%d').date() if next_calibration_date else None,
            calibration_frequency_months=int(calibration_frequency_months),
            status=status,
            created_by=request.user
        )
        
        # Log de création
        ToolHistory.log_action(
            tool=tool,
            user=request.user,
            action='created',
            description=f"Outil créé par {request.user.username}",
            request=request
        )
        
        logger.info(f"🛠️ Nouvel outil créé: {description} par {request.user.username}")
        messages.success(request, f"L'outil {description} a été créé avec succès !")
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
        # Récupérer les anciennes valeurs
        old_description = tool.description
        old_number = tool.number
        old_status = tool.status
        old_location = tool.location
        
        description = request.POST.get('description')
        number = request.POST.get('number')
        tool_description = request.POST.get('tool_description', '')
        manufacturer = request.POST.get('manufacturer', '')
        tool_type = request.POST.get('tool_type', '')
        location = request.POST.get('location', '')
        next_calibration_date = request.POST.get('next_calibration_date')
        calibration_frequency_months = request.POST.get('calibration_frequency_months', 6)
        status = request.POST.get('status', 'active')
        
        if not description or not number:
            messages.error(request, "Le nom et le numéro de série sont obligatoires")
            return render(request, 'tools/edit_tool.html', {'tool': tool})
        
        from datetime import datetime as dt
        tool.description = description
        tool.number = number
        tool.tool_description = tool_description
        tool.manufacturer = manufacturer
        tool.tool_type = tool_type
        tool.location = location
        if next_calibration_date:
            tool.next_calibration_date = dt.strptime(next_calibration_date, '%Y-%m-%d').date()
        tool.calibration_frequency_months = int(calibration_frequency_months)
        tool.status = status
        tool.save()
        
        # Log des modifications
        changes = []
        if old_description != description:
            changes.append("Description")
        if old_number != number:
            changes.append("Numéro de série")
        if old_status != status:
            changes.append("Statut")
        if old_location != location:
            changes.append("Emplacement")
        
        if changes:
            ToolHistory.log_action(
                tool=tool,
                user=request.user,
                action='updated',
                description=f"Modification de {', '.join(changes)} par {request.user.username}",
                field_name=', '.join(changes),
                old_value=f"Anciennes valeurs: {old_description}, {old_number}",
                new_value=f"Nouvelles valeurs: {description}, {number}",
                request=request
            )
        
        logger.info(f"✏️ Outil modifié: {description} par {request.user.username}")
        messages.success(request, f"✅ L'outil {description} a été modifié avec succès !")
        return redirect('tools:tool_list')
    
    return render(request, 'tools/edit_tool.html', {'tool': tool})


@login_required
def delete_tool(request, tool_id):
    """Supprimer un outil (réservé aux Supervisors)"""
    tool = get_object_or_404(Tool, id=tool_id)
    
    if not request.user.is_superuser:
        messages.error(request, "❌ Seul un Superviseur peut supprimer des outils")
        return redirect('tools:tool_list')
    
    if request.method == 'POST':
        tool_name = tool.description
        
        # Log de suppression
        ToolHistory.log_action(
            tool=tool,
            user=request.user,
            action='deleted',
            description=f"Outil supprimé par {request.user.username}",
            old_value=f"Nom: {tool_name}, N° série: {tool.number}",
            request=request
        )
        
        tool.delete()
        logger.info(f"🗑️ Outil supprimé: {tool_name} par {request.user.username}")
        messages.success(request, f"🗑️ L'outil {tool_name} a été supprimé avec succès !")
        return redirect('tools:tool_list')
    
    return render(request, 'tools/delete_tool.html', {'tool': tool})


# ===== FONCTIONS D'EXPORT =====

@login_required
def export_tools_pdf(request):
    """Exporter la liste des outils en PDF"""
    
    tools = Tool.objects.all().order_by('description')
    
    search = request.GET.get('search', '')
    if search:
        tools = tools.filter(
            Q(description__icontains=search) |
            Q(number__icontains=search) |
            Q(tool_description__icontains=search) |
            Q(manufacturer__icontains=search) |
            Q(location__icontains=search)
        )
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        tools = tools.filter(status=status_filter)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="outils_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=20
    )
    elements.append(Paragraph("Liste des outils - Tool Calibration", title_style))
    elements.append(Spacer(1, 10))
    
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT,
        textColor=colors.grey
    )
    elements.append(Paragraph(f"Généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M')}", date_style))
    elements.append(Spacer(1, 20))
    
    stat_style = ParagraphStyle(
        'StatStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT
    )
    elements.append(Paragraph(f"Total des outils : {tools.count()}", stat_style))
    if search:
        elements.append(Paragraph(f"Recherche : {search}", stat_style))
    if status_filter:
        elements.append(Paragraph(f"Statut : {status_filter}", stat_style))
    elements.append(Spacer(1, 15))
    
    data = []
    data.append([
        'N°', 'Internal N°', 'GPN', 'N° Série', 'Description', 
        'Fabricant', 'Type', 'Statut', 'Prochain étalonnage', 'Emplacement', 'Alerte'
    ])
    
    for idx, tool in enumerate(tools, 1):
        today = date.today()
        days = (tool.next_calibration_date - today).days
        if days < 0:
            alert = '🔴 En retard'
        elif days <= 7:
            alert = '🔴 Urgent'
        elif days <= 30:
            alert = '🟡 Bientôt'
        elif days <= 60:
            alert = '🟢 À prévoir'
        else:
            alert = '✅ OK'
        
        data.append([
            str(idx),
            tool.internal_number or '-',
            tool.gpn or '-',
            tool.number,
            tool.description,
            tool.manufacturer or '-',
            tool.tool_type or '-',
            tool.get_status_display(),
            tool.next_calibration_date.strftime('%d/%m/%Y'),
            tool.location or '-',
            alert
        ])
    
    table = Table(data, colWidths=[1*cm, 3*cm, 3*cm, 3*cm, 4*cm, 3*cm, 2.5*cm, 2.5*cm, 3*cm, 2.5*cm, 3*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (7, 1), (7, -1), 'CENTER'),
        ('ALIGN', (8, 1), (8, -1), 'CENTER'),
        ('ALIGN', (10, 1), (10, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#1a1a2e')),
    ]))
    
    elements.append(table)
    
    elements.append(Spacer(1, 20))
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    elements.append(Paragraph("Tool Calibration Tracking System - Document généré automatiquement", footer_style))
    
    doc.build(elements)
    return response


@login_required
def export_tools_excel(request):
    """Exporter la liste des outils en Excel"""
    
    tools = Tool.objects.all().order_by('description')
    
    search = request.GET.get('search', '')
    if search:
        tools = tools.filter(
            Q(description__icontains=search) |
            Q(number__icontains=search) |
            Q(tool_description__icontains=search) |
            Q(manufacturer__icontains=search) |
            Q(location__icontains=search)
        )
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        tools = tools.filter(status=status_filter)
    
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#1a1a2e',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'font_size': 9
    })
    
    cell_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter',
        'font_size': 8
    })
    
    date_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'font_size': 8,
        'num_format': 'dd/mm/yyyy'
    })
    
    center_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'font_size': 8
    })
    
    worksheet = workbook.add_worksheet('Outils')
    
    worksheet.merge_range('A1:K1', 'Liste des outils - Tool Calibration', header_format)
    worksheet.write(2, 0, f"Généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    worksheet.write(3, 0, f"Total : {tools.count()} outils")
    
    headers = ['N°', 'Internal N°', 'GPN', 'N° Série', 'Description', 
               'Fabricant', 'Type', 'Statut', 'Prochain étalonnage', 'Emplacement', 'Alerte']
    for col, header in enumerate(headers):
        worksheet.write(5, col, header, header_format)
    
    row = 6
    today = date.today()
    for idx, tool in enumerate(tools, 1):
        days = (tool.next_calibration_date - today).days
        if days < 0:
            alert = '🔴 En retard'
        elif days <= 7:
            alert = '🔴 Urgent'
        elif days <= 30:
            alert = '🟡 Bientôt'
        elif days <= 60:
            alert = '🟢 À prévoir'
        else:
            alert = '✅ OK'
        
        worksheet.write(row, 0, idx, center_format)
        worksheet.write(row, 1, tool.internal_number or '-', cell_format)
        worksheet.write(row, 2, tool.gpn or '-', cell_format)
        worksheet.write(row, 3, tool.number, cell_format)
        worksheet.write(row, 4, tool.description, cell_format)
        worksheet.write(row, 5, tool.manufacturer or '-', cell_format)
        worksheet.write(row, 6, tool.tool_type or '-', cell_format)
        worksheet.write(row, 7, tool.get_status_display(), center_format)
        worksheet.write(row, 8, tool.next_calibration_date.strftime('%d/%m/%Y'), date_format)
        worksheet.write(row, 9, tool.location or '-', cell_format)
        worksheet.write(row, 10, alert, center_format)
        row += 1
    
    worksheet.set_column('A:A', 5)
    worksheet.set_column('B:B', 14)
    worksheet.set_column('C:C', 14)
    worksheet.set_column('D:D', 14)
    worksheet.set_column('E:E', 30)
    worksheet.set_column('F:F', 18)
    worksheet.set_column('G:G', 16)
    worksheet.set_column('H:H', 14)
    worksheet.set_column('I:I', 16)
    worksheet.set_column('J:J', 18)
    worksheet.set_column('K:K', 14)
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="outils_{datetime.now().strftime("%Y%m%d")}.xlsx"'
    return response


@login_required
def export_alerts_pdf(request):
    """Exporter les alertes en PDF"""
    
    today = date.today()
    alert_tools = Tool.objects.filter(
        Q(next_calibration_date__lte=today + timedelta(days=60)) &
        Q(status__in=['active', 'down'])
    ).order_by('next_calibration_date')
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="alertes_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.HexColor('#dc2626')
    )
    elements.append(Paragraph("Rapport des alertes - Tool Calibration", title_style))
    elements.append(Spacer(1, 10))
    
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT,
        textColor=colors.grey
    )
    elements.append(Paragraph(f"Généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M')}", date_style))
    elements.append(Spacer(1, 15))
    
    stat_style = ParagraphStyle(
        'StatStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT
    )
    elements.append(Paragraph(f"Total des alertes : {alert_tools.count()}", stat_style))
    
    overdue_count = alert_tools.filter(next_calibration_date__lt=today).count()
    red_count = alert_tools.filter(
        next_calibration_date__gte=today,
        next_calibration_date__lte=today + timedelta(days=7)
    ).count()
    yellow_count = alert_tools.filter(
        next_calibration_date__gt=today + timedelta(days=7),
        next_calibration_date__lte=today + timedelta(days=30)
    ).count()
    green_count = alert_tools.filter(
        next_calibration_date__gt=today + timedelta(days=30),
        next_calibration_date__lte=today + timedelta(days=60)
    ).count()
    
    elements.append(Paragraph(f"🔴 En retard : {overdue_count} | 🔴 Urgent : {red_count} | 🟡 Bientôt : {yellow_count} | 🟢 À prévoir : {green_count}", stat_style))
    elements.append(Spacer(1, 15))
    
    data = []
    data.append(['Niveau', 'N° Série', 'Description', 'Fabricant', 'Date échéance', 'Jours restants', 'Emplacement'])
    
    for tool in alert_tools:
        days = (tool.next_calibration_date - today).days
        if days < 0:
            level = '🔴 En retard'
        elif days <= 7:
            level = '🔴 Urgent'
        elif days <= 30:
            level = '🟡 Bientôt'
        elif days <= 60:
            level = '🟢 À prévoir'
        else:
            level = '✅ OK'
        
        data.append([
            level,
            tool.number,
            tool.description,
            tool.manufacturer or '-',
            tool.next_calibration_date.strftime('%d/%m/%Y'),
            f"{days} jours",
            tool.location or '-'
        ])
    
    table = Table(data, colWidths=[3*cm, 3.5*cm, 4.5*cm, 3.5*cm, 3*cm, 2.5*cm, 3.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (4, 1), (4, -1), 'CENTER'),
        ('ALIGN', (5, 1), (5, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#dc2626')),
    ]))
    
    elements.append(table)
    
    elements.append(Spacer(1, 20))
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    elements.append(Paragraph("Tool Calibration Tracking System - Document généré automatiquement", footer_style))
    
    doc.build(elements)
    return response


# ===== FONCTIONS D'IMPORT AVEC CSV =====

@login_required
def download_template_excel(request):
    """Télécharger le template Excel pour l'import"""
    
    columns = [
        'LP', 'internal number', 'GPN', 'Tool type', 'Tool index', 'Number',
        'Description', 'Manufacturer', 'Tool description', 'connector of number',
        'First calibration', 'Next calibration date', 'department',
        'calibration tracabilty', 'reception tracabilty', 'name, surname',
        'Location', 'comments', 'Order No', 'Status reception', 'validation satus'
    ]
    
    df = pd.DataFrame(columns=columns)
    
    example_data = {
        'LP': 1,
        'internal number': 'N000000001',
        'GPN': 'T2000000000001.000',
        'Tool type': 'standard hand tool',
        'Tool index': 'N*001',
        'Number': '001-1',
        'Description': 'Exemple d\'outil',
        'Manufacturer': 'HOFFMANN',
        'Tool description': 'Description de l\'outil',
        'connector of number': '',
        'First calibration': '2026-01-27',
        'Next calibration date': '2026-07-26',
        'department': 'Ba-Wu - Main wesser - LNVG',
        'calibration tracabilty': '',
        'reception tracabilty': '',
        'name, surname': '',
        'Location': 'Training center',
        'comments': '',
        'Order No': '32000032',
        'Status reception': 'Received',
        'validation satus': '32000032'
    }
    df.loc[0] = example_data
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Tools', index=False)
        
        workbook = writer.book
        sheet = workbook['Tools']
        for col in sheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            sheet.column_dimensions[column].width = adjusted_width
        
        instructions_df = pd.DataFrame({
            'Instructions': [
                '📋 GUIDE D\'IMPORT',
                '',
                '1. Colonnes obligatoires:',
                '   - Number (Numéro de série unique)',
                '   - Description (Nom de l\'outil)',
                '',
                '2. Colonnes recommandées:',
                '   - Manufacturer (Fabricant)',
                '   - Tool type (Type d\'outil)',
                '   - Location (Emplacement)',
                '   - Next calibration date (Prochain étalonnage)',
                '',
                '3. Formats de date acceptés:',
                '   - 2026-07-26 (Recommandé)',
                '   - 26/07/2026',
                '   - 07/26/2026',
                '',
                '4. Ne modifiez pas les noms des colonnes !',
                '',
                '📧 Support: contact@toolcalibration.com'
            ]
        })
        instructions_df.to_excel(writer, sheet_name='Instructions', index=False)
    
    output.seek(0)
    
    response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="template_import_outils.xlsx"'
    return response


@login_required
def download_template_csv(request):
    """Télécharger le template CSV pour l'import"""
    
    columns = [
        'LP', 'internal number', 'GPN', 'Tool type', 'Tool index', 'Number',
        'Description', 'Manufacturer', 'Tool description', 'connector of number',
        'First calibration', 'Next calibration date', 'department',
        'calibration tracabilty', 'reception tracabilty', 'name, surname',
        'Location', 'comments', 'Order No', 'Status reception', 'validation satus'
    ]
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="template_import_outils.csv"'
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(columns)
    
    example_row = [
        '1', 'N000000001', 'T2000000000001.000', 'standard hand tool', 'N*001', '001-1',
        'Exemple d\'outil', 'HOFFMANN', 'Description de l\'outil', '',
        '2026-01-27', '2026-07-26', 'Ba-Wu - Main wesser - LNVG',
        '', '', '', 'Training center', '', '32000032', 'Received', '32000032'
    ]
    writer.writerow(example_row)
    
    writer.writerow([])
    writer.writerow(['📋 GUIDE D\'IMPORT CSV'])
    writer.writerow(['Colonnes obligatoires: Number, Description'])
    writer.writerow(['Format date: YYYY-MM-DD'])
    writer.writerow(['Séparateur: ;'])
    writer.writerow(['Encodage: UTF-8'])
    
    return response


@login_required
def import_tools(request):
    """Interface d'import d'outils depuis Excel ou CSV"""
    
    context = {'step': 'upload'}
    
    if request.method == 'POST':
        if 'confirm_import' in request.POST:
            return process_import(request)
        
        if 'excel_file' not in request.FILES:
            messages.error(request, "Veuillez sélectionner un fichier")
            return render(request, 'tools/import_tools.html', context)
        
        excel_file = request.FILES['excel_file']
        file_name = excel_file.name.lower()
        
        if not (file_name.endswith(('.xlsx', '.xls', '.csv'))):
            messages.error(request, "Veuillez uploader un fichier Excel (.xlsx, .xls) ou CSV (.csv)")
            return render(request, 'tools/import_tools.html', context)
        
        try:
            if file_name.endswith('.csv'):
                raw_data = excel_file.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
                excel_file.seek(0)
                
                try:
                    df = pd.read_csv(excel_file, encoding=encoding, sep=';', header=3)
                except:
                    excel_file.seek(0)
                    try:
                        df = pd.read_csv(excel_file, encoding=encoding, sep=',', header=3)
                    except:
                        df = pd.read_csv(excel_file, encoding='utf-8', sep=';', header=3)
            else:
                df = pd.read_excel(excel_file, header=3)
            
            df.columns = df.columns.str.strip()
            
            column_mapping = {
                'LP': 'lp',
                'internal number': 'internal_number',
                'GPN': 'gpn',
                'Tool type': 'tool_type',
                'Tool index': 'tool_index',
                'Number': 'number',
                'Description': 'description',
                'Manufacturer': 'manufacturer',
                'Tool description': 'tool_description',
                'connector of number': 'connector_number',
                'First calibration': 'first_calibration',
                'Next calibration date': 'next_calibration_date',
                'department': 'department',
                'calibration tracabilty': 'calibration_tracability',
                'reception tracabilty': 'reception_tracability',
                'name, surname': 'name_surname',
                'Location': 'location',
                'comments': 'comments',
                'Order No': 'order_no',
                'Status reception': 'status_reception',
                'validation satus': 'validation_status'
            }
            
            existing_columns = {}
            for excel_col, django_field in column_mapping.items():
                if excel_col in df.columns:
                    existing_columns[excel_col] = django_field
            
            df_filtered = df[list(existing_columns.keys())].copy()
            df_filtered.columns = [existing_columns[col] for col in df_filtered.columns]
            
            data_records = df_filtered.to_dict('records')
            
            for record in data_records:
                for key, value in record.items():
                    if isinstance(value, (datetime, date, pd.Timestamp)):
                        record[key] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
                    elif pd.isna(value):
                        record[key] = None
                    elif isinstance(value, float) and value.is_integer():
                        record[key] = int(value)
            
            request.session['import_data'] = data_records
            request.session['import_columns'] = list(df_filtered.columns)
            request.session['original_columns'] = list(existing_columns.keys())
            
            preview_data = data_records[:5] if len(data_records) >= 5 else data_records
            
            context = {
                'step': 'mapping',
                'columns': list(df_filtered.columns),
                'original_columns': list(existing_columns.keys()),
                'preview': preview_data,
                'total_rows': len(df_filtered),
                'file_name': excel_file.name,
            }
            
            return render(request, 'tools/import_tools.html', context)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la lecture du fichier : {str(e)}")
            return render(request, 'tools/import_tools.html', {'step': 'upload'})
    
    return render(request, 'tools/import_tools.html', context)


def process_import(request):
    """Traiter l'import des données"""
    
    if request.method != 'POST':
        return redirect('tools:import_tools')
    
    data = request.session.get('import_data', [])
    if not data:
        messages.error(request, "Aucune donnée à importer")
        return redirect('tools:import_tools')
    
    field_mapping = {}
    for key in request.POST:
        if key.startswith('map_'):
            field_name = key.replace('map_', '')
            excel_column = request.POST.get(key)
            if excel_column:
                field_mapping[field_name] = excel_column
    
    skip_duplicates = request.POST.get('skip_duplicates') == 'on'
    update_existing = request.POST.get('update_existing') == 'on'
    
    stats = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'error_details': []
    }
    
    user = request.user
    
    for idx, row_data in enumerate(data):
        try:
            tool_data = {}
            for field, column in field_mapping.items():
                value = row_data.get(column)
                if isinstance(value, str) and field in ['next_calibration_date', 'first_calibration']:
                    try:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except:
                        value = None
                tool_data[field] = value
            
            if not tool_data.get('description') or not tool_data.get('number'):
                stats['skipped'] += 1
                continue
            
            existing = Tool.objects.filter(number=tool_data['number']).first()
            
            if existing:
                if update_existing:
                    for field, value in tool_data.items():
                        if value is not None and hasattr(existing, field):
                            setattr(existing, field, value)
                    existing.save()
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1
            else:
                tool = Tool(
                    lp=tool_data.get('lp'),
                    internal_number=tool_data.get('internal_number'),
                    gpn=tool_data.get('gpn'),
                    tool_type=tool_data.get('tool_type'),
                    tool_index=tool_data.get('tool_index'),
                    number=tool_data.get('number'),
                    description=tool_data.get('description'),
                    manufacturer=tool_data.get('manufacturer'),
                    tool_description=tool_data.get('tool_description'),
                    connector_number=tool_data.get('connector_number'),
                    first_calibration=tool_data.get('first_calibration'),
                    next_calibration_date=tool_data.get('next_calibration_date') or datetime.now().date(),
                    department=tool_data.get('department'),
                    calibration_tracability=tool_data.get('calibration_tracability'),
                    reception_tracability=tool_data.get('reception_tracability'),
                    name_surname=tool_data.get('name_surname'),
                    location=tool_data.get('location'),
                    comments=tool_data.get('comments'),
                    order_no=tool_data.get('order_no'),
                    status_reception=tool_data.get('status_reception'),
                    validation_status=tool_data.get('validation_status'),
                    status='active',
                    created_by=user
                )
                tool.save()
                stats['created'] += 1
                
        except Exception as e:
            stats['errors'] += 1
            stats['error_details'].append(f"Ligne {idx+1}: {str(e)}")
    
    request.session.pop('import_data', None)
    request.session.pop('import_columns', None)
    request.session.pop('original_columns', None)
    
    message = f"✅ Import terminé ! Créés: {stats['created']}, Mis à jour: {stats['updated']}, Ignorés: {stats['skipped']}, Erreurs: {stats['errors']}"
    messages.success(request, message)
    
    if stats['error_details']:
        for error in stats['error_details'][:5]:
            messages.warning(request, error)
    
    return render(request, 'tools/import_tools.html', {
        'step': 'result',
        'stats': stats
    })