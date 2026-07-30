#!/usr/bin/env python
import os
import sys
import django
import pandas as pd
from datetime import datetime, timedelta

# Configurer Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tools.models import Tool
from django.contrib.auth.models import User

def import_tools_from_excel(file_path):
    """Importe les outils depuis un fichier Excel avec tous les champs"""
    
    print(f"📁 Lecture du fichier: {file_path}")
    
    try:
        # Lire le fichier Excel
        df = pd.read_excel(file_path, sheet_name='Tools', header=3)
        
        print(f"📊 {len(df)} lignes trouvées")
        print(f"📋 Colonnes disponibles: {list(df.columns)}")
        
        # Récupérer le superuser
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            print("❌ Aucun superuser trouvé ! Crée-en un avec: python manage.py createsuperuser")
            return
        
        print(f"👤 Utilisateur: {user.username}")
        print("="*60)
        
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
                
                # --- EXTRAIRE LES DONNÉES ---
                
                # 1. Nom de l'outil (Description)
                name = str(row.get('Description', '')).strip()
                if not name or name == 'nan' or name == 'None':
                    skipped += 1
                    continue
                
                # 2. Numéro de série (Number)
                serial = str(row.get('Number', '')).strip()
                if not serial or serial == 'nan' or serial == 'None':
                    serial = f"AUTO-{index:04d}"
                    print(f"⚠️ Ligne {index}: Numéro de série généré: {serial}")
                
                # 3. Type d'outil (Tool type)
                tool_type = str(row.get('Tool type', '')).strip()
                if tool_type == 'nan' or tool_type == 'None':
                    tool_type = ''
                
                # 4. Fabricant (Manufacturer)
                manufacturer = str(row.get('Manufacturer', '')).strip()
                if manufacturer == 'nan' or manufacturer == 'None':
                    manufacturer = ''
                
                # 5. Description combinée
                description = f"{tool_type} - {manufacturer}".strip()
                if description == '-' or description == '':
                    description = name
                
                # 6. GPN
                gpn = str(row.get('GPN', '')).strip()
                if gpn == 'nan' or gpn == 'None':
                    gpn = ''
                
                # 7. Numéro interne (internal number)
                internal_number = str(row.get('internal number', '')).strip()
                if internal_number == 'nan' or internal_number == 'None':
                    internal_number = ''
                
                # 8. Département (department)
                department = str(row.get('department', '')).strip()
                if department == 'nan' or department == 'None':
                    department = ''
                
                # 9. Localisation (Location)
                location = str(row.get('Location', '')).strip()
                if location == 'nan' or location == 'None':
                    location = ''
                
                # 10. Commentaires (comments)
                comments = str(row.get('comments', '')).strip()
                if comments == 'nan' or comments == 'None':
                    comments = ''
                
                # 11. Statut réception (Status reception)
                status_reception = str(row.get('Status reception', '')).strip()
                if status_reception == 'nan' or status_reception == 'None':
                    status_reception = ''
                
                # 12. Statut validation (validation satus)
                validation_status = str(row.get('validation satus', '')).strip()
                if validation_status == 'nan' or validation_status == 'None':
                    validation_status = ''
                
                # 13. Première calibration (First calibration)
                first_cal = row.get('First calibration')
                if pd.isna(first_cal) or first_cal is None:
                    first_calibration_date = None
                elif isinstance(first_cal, (pd.Timestamp, datetime)):
                    first_calibration_date = first_cal.date()
                elif isinstance(first_cal, str):
                    try:
                        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d.%m.%Y']:
                            try:
                                first_calibration_date = datetime.strptime(first_cal, fmt).date()
                                break
                            except:
                                continue
                    except:
                        first_calibration_date = None
                else:
                    first_calibration_date = None
                
                # 14. Prochaine calibration (Next calibration date)
                next_cal = row.get('Next calibration date')
                if pd.isna(next_cal) or next_cal is None:
                    if first_calibration_date:
                        next_cal = first_calibration_date + timedelta(days=180)
                    else:
                        next_cal = datetime.now().date() + timedelta(days=180)
                elif isinstance(next_cal, (pd.Timestamp, datetime)):
                    next_cal = next_cal.date()
                elif isinstance(next_cal, str):
                    try:
                        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d.%m.%Y']:
                            try:
                                next_cal = datetime.strptime(next_cal, fmt).date()
                                break
                            except:
                                continue
                    except:
                        next_cal = datetime.now().date() + timedelta(days=180)
                else:
                    next_cal = datetime.now().date() + timedelta(days=180)
                
                # 15. Statut Django (basé sur validation_status)
                val_lower = validation_status.lower()
                if 'done' in val_lower or val_lower == 'done':
                    status = 'active'
                elif 'under validation' in val_lower:
                    status = 'under_calibration'
                elif 'not yet' in val_lower or 'customs' in val_lower:
                    status = 'lost'
                elif 'shipping' in val_lower:
                    status = 'active'
                else:
                    status = 'active'
                
                # --- CRÉER OU METTRE À JOUR ---
                
                # Vérifier si l'outil existe déjà
                existing = Tool.objects.filter(serial_number=serial).first()
                
                if existing:
                    # Mettre à jour
                    existing.name = name
                    existing.description = description
                    existing.manufacturer = manufacturer
                    existing.tool_type = tool_type
                    existing.department = department
                    existing.location = location
                    existing.comments = comments
                    existing.status_reception = status_reception
                    existing.validation_status = validation_status
                    existing.gpn = gpn
                    existing.internal_number = internal_number
                    existing.first_calibration_date = first_calibration_date
                    existing.next_calibration_date = next_cal
                    existing.status = status
                    existing.save()
                    updated += 1
                    print(f"🔄 Mis à jour: {name} ({serial})")
                else:
                    # Créer
                    tool = Tool.objects.create(
                        name=name,
                        serial_number=serial,
                        description=description,
                        manufacturer=manufacturer,
                        tool_type=tool_type,
                        department=department,
                        location=location,
                        comments=comments,
                        status_reception=status_reception,
                        validation_status=validation_status,
                        gpn=gpn,
                        internal_number=internal_number,
                        first_calibration_date=first_calibration_date,
                        next_calibration_date=next_cal,
                        purchase_date=None,
                        calibration_frequency_months=6,
                        status=status,
                        created_by=user
                    )
                    created += 1
                    print(f"✅ Créé: {name} ({serial})")
                    
            except Exception as e:
                errors += 1
                print(f"❌ Erreur ligne {index}: {str(e)}")
                if errors > 20:
                    print("⚠️ Trop d'erreurs, arrêt...")
                    break
        
        # Résumé
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DE L'IMPORT")
        print(f"   ✅ Créés: {created}")
        print(f"   🔄 Mis à jour: {updated}")
        print(f"   ⏭️ Ignorés: {skipped}")
        print(f"   ❌ Erreurs: {errors}")
        print(f"   📊 Total lignes: {len(df)}")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Chemin vers ton fichier
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "Copy of TOOLLIST_Follow Up New 30.06.2026.xls"
    
    import_tools_from_excel(file_path)