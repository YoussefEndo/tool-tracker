import pandas as pd
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tools.models import Tool
from datetime import datetime, timedelta
import re
import os

class Command(BaseCommand):
    help = 'Import tools from Excel file (.xls or .xlsx)'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the Excel file')
        parser.add_argument(
            '--sheet',
            type=str,
            default='Tools',
            help='Sheet name to import (default: Tools)'
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        sheet_name = options['sheet']
        
        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"❌ File not found: {file_path}"))
            return
        
        self.stdout.write(f"📁 Reading file: {file_path}")
        self.stdout.write(f"📄 Sheet: {sheet_name}")
        
        try:
            # Lire le fichier Excel (gère .xls et .xlsx)
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=3)
            
            # Nettoyer les noms de colonnes
            df.columns = df.columns.str.strip()
            
            self.stdout.write(f"📊 Found {len(df)} rows")
            
            # Récupérer l'utilisateur
            default_user = User.objects.filter(is_superuser=True).first()
            
            if not default_user:
                self.stdout.write(self.style.WARNING("⚠️ No superuser found. Please create one: python manage.py createsuperuser"))
                return
            
            # Compteurs
            created = 0
            updated = 0
            skipped = 0
            errors = 0
            
            for index, row in df.iterrows():
                try:
                    # Ignorer les lignes vides
                    if pd.isna(row.get('LP')) and pd.isna(row.get('Description')):
                        skipped += 1
                        continue
                    
                    # Extraire les données
                    name = str(row.get('Description', '')).strip()
                    serial_number = str(row.get('Number', '')).strip()
                    
                    # Si le nom ou le numéro de série est vide, on saute
                    if not name or name == 'nan' or name == 'None':
                        skipped += 1
                        continue
                    
                    if not serial_number or serial_number == 'nan' or serial_number == 'None':
                        # Si pas de numéro de série, on utilise l'index + nom
                        serial_number = f"AUTO-{index:04d}-{name[:10]}"
                        self.stdout.write(self.style.WARNING(f"⚠️ No serial number, generated: {serial_number}"))
                    
                    # Gérer les dates
                    first_cal = row.get('First calibration')
                    next_cal = row.get('Next calibration date')
                    
                    # Convertir les dates
                    if pd.isna(next_cal) or next_cal is None:
                        # Si pas de prochaine date, on met une date par défaut (dans 6 mois)
                        next_cal = datetime.now().date() + timedelta(days=180)
                    else:
                        # Si c'est une chaîne, on essaie de la convertir
                        if isinstance(next_cal, str):
                            try:
                                # Essayer différents formats
                                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']:
                                    try:
                                        next_cal = datetime.strptime(next_cal, fmt).date()
                                        break
                                    except:
                                        continue
                            except:
                                next_cal = datetime.now().date() + timedelta(days=180)
                        elif hasattr(next_cal, 'date'):
                            next_cal = next_cal.date()
                    
                    # Extraire le statut
                    validation_status = str(row.get('validation satus', '')).strip().lower()
                    status_reception = str(row.get('Status reception', '')).strip().lower()
                    
                    if 'done' in validation_status or validation_status == 'done':
                        tool_status = 'active'
                    elif 'under validation' in validation_status:
                        tool_status = 'under_calibration'
                    elif 'not yet' in validation_status or 'customs' in validation_status:
                        tool_status = 'active'
                    elif 'shipping' in validation_status:
                        tool_status = 'active'
                    elif 'waiting' in validation_status:
                        tool_status = 'active'
                    else:
                        tool_status = 'active'
                    
                    # Extraire la localisation
                    location = str(row.get('Location', '')).strip()
                    if location == 'nan' or location == 'None':
                        location = ''
                    
                    # Extraire le fabricant
                    manufacturer = str(row.get('Manufacturer', '')).strip()
                    if manufacturer == 'nan' or manufacturer == 'None':
                        manufacturer = ''
                    
                    # Extraire le type
                    tool_type = str(row.get('Tool type', '')).strip()
                    if tool_type == 'nan' or tool_type == 'None':
                        tool_type = ''
                    
                    # Construire la description
                    description = f"{tool_type} - {manufacturer}".strip()
                    if description == '-':
                        description = ''
                    
                    # Créer ou mettre à jour l'outil
                    tool, created_flag = Tool.objects.get_or_create(
                        serial_number=serial_number,
                        defaults={
                            'name': name,
                            'description': description,
                            'purchase_date': None,
                            'calibration_frequency_months': 6,
                            'next_calibration_date': next_cal,
                            'status': tool_status,
                            'location': location,
                            'created_by': default_user,
                        }
                    )
                    
                    if created_flag:
                        created += 1
                        self.stdout.write(f"✅ Created: {name} - {serial_number}")
                    else:
                        # Mettre à jour si existant
                        tool.name = name
                        tool.description = description
                        tool.location = location
                        tool.status = tool_status
                        tool.next_calibration_date = next_cal
                        tool.save()
                        updated += 1
                        self.stdout.write(f"🔄 Updated: {name} - {serial_number}")
                        
                except Exception as e:
                    errors += 1
                    self.stdout.write(self.style.ERROR(f"❌ Error on row {index}: {str(e)}"))
            
            # Résumé
            total = len(df)
            self.stdout.write(self.style.SUCCESS(f"\n🎉 Import completed!"))
            self.stdout.write(f"   ✅ Created: {created}")
            self.stdout.write(f"   🔄 Updated: {updated}")
            self.stdout.write(f"   ⏭️ Skipped: {skipped}")
            self.stdout.write(f"   ❌ Errors: {errors}")
            self.stdout.write(f"   📊 Total rows: {total}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error reading file: {str(e)}"))
            self.stdout.write(self.style.ERROR("Try: pip install xlrd openpyxl"))