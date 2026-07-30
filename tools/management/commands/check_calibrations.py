from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Q
from tools.models import Tool, ToolHistory
from datetime import date, timedelta
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Vérifie les dates d\'étalonnage et envoie des alertes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            action='store_true',
            help='Envoyer des emails d\'alerte',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simuler l\'exécution sans envoyer d\'emails',
        )

    def handle(self, *args, **options):
        today = date.today()
        dry_run = options.get('dry_run', False)
        send_emails = options.get('email', False)
        
        self.stdout.write(self.style.SUCCESS(f'🔍 Vérification des étalonnages - {today}'))
        self.stdout.write('=' * 60)
        
        # Récupérer les outils actifs
        tools = Tool.objects.filter(
            status__in=['active', 'down']
        )
        
        alerts = {
            'overdue': [],
            'red': [],
            'yellow': [],
            'green': [],
        }
        
        for tool in tools:
            days_until = (tool.next_calibration_date - today).days
            
            if days_until < 0:
                alerts['overdue'].append(tool)
                tool.alert_level = 'red'  # Mettre à jour l'alerte
                tool.save()
            elif days_until <= 7:
                alerts['red'].append(tool)
                tool.alert_level = 'red'
                tool.save()
            elif days_until <= 30:
                alerts['yellow'].append(tool)
                tool.alert_level = 'yellow'
                tool.save()
            elif days_until <= 60:
                alerts['green'].append(tool)
                tool.alert_level = 'green'
                tool.save()
            else:
                # Pas d'alerte
                if tool.alert_level != 'none':
                    tool.alert_level = 'none'
                    tool.save()
        
        # Afficher les résultats
        self.stdout.write(f'\n📊 RÉSULTATS:')
        self.stdout.write(f'   🔴 En retard: {len(alerts["overdue"])}')
        self.stdout.write(f'   🔴 Rouge (≤7j): {len(alerts["red"])}')
        self.stdout.write(f'   🟡 Jaune (≤30j): {len(alerts["yellow"])}')
        self.stdout.write(f'   🟢 Vert (≤60j): {len(alerts["green"])}')
        
        # Afficher les détails
        for level, color in [('overdue', '🔴'), ('red', '🔴'), ('yellow', '🟡'), ('green', '🟢')]:
            if alerts[level]:
                self.stdout.write(f'\n{color} {level.upper()} ({len(alerts[level])} outils):')
                for tool in alerts[level][:5]:
                    days = (tool.next_calibration_date - today).days
                    self.stdout.write(f'   - {tool.name} ({tool.serial_number}) - {days} jours')
                if len(alerts[level]) > 5:
                    self.stdout.write(f'   ... et {len(alerts[level]) - 5} autres')
        
        # Envoyer des emails si demandé
        if send_emails and not dry_run:
            self.send_alerts_email(alerts, today)
            self.stdout.write(self.style.SUCCESS('\n📧 Emails envoyés !'))
        elif send_emails and dry_run:
            self.stdout.write(self.style.WARNING('\n📧 Mode DRY-RUN : Aucun email envoyé'))
        
        # Logging
        total_alerts = sum(len(v) for v in alerts.values())
        logger.info(f'Alertes vérifiées: {total_alerts} alertes trouvées sur {tools.count()} outils')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Vérification terminée !'))
    
    def send_alerts_email(self, alerts, today):
        """Envoyer un email récapitulatif des alertes"""
        
        # Récupérer les supervisors
        supervisors = User.objects.filter(
            Q(is_superuser=True) | Q(groups__name='Supervisor')
        ).distinct()
        
        if not supervisors:
            self.stdout.write(self.style.WARNING('⚠️ Aucun superviseur trouvé pour les emails'))
            return
        
        # Construire le message
        subject = f'[Tool Calibration] Alertes du {today.strftime("%d/%m/%Y")}'
        
        total_alerts = sum(len(v) for v in alerts.values())
        
        body = f"""
        📋 RAPPORT D'ALERTES - {today.strftime("%d/%m/%Y")}
        
        {'='*50}
        
        🔴 EN RETARD: {len(alerts['overdue'])}
        🔴 ROUGE (≤7j): {len(alerts['red'])}
        🟡 JAUNE (≤30j): {len(alerts['yellow'])}
        🟢 VERT (≤60j): {len(alerts['green'])}
        
        {'='*50}
        TOTAL: {total_alerts} alertes actives
        
        """
        
        # Détails par niveau
        for level, emoji in [('overdue', '🔴'), ('red', '🔴'), ('yellow', '🟡'), ('green', '🟢')]:
            if alerts[level]:
                body += f'\n{emoji} {level.upper()} ({len(alerts[level])}):\n'
                for tool in alerts[level]:
                    days = (tool.next_calibration_date - today).days
                    body += f'   - {tool.name} ({tool.serial_number}) - {days} jours\n'
        
        body += '\n' + '='*50 + '\n'
        body += '🌐 Connectez-vous pour plus de détails: http://127.0.0.1:8000/\n'
        
        # Envoyer à chaque supervisor
        for supervisor in supervisors:
            try:
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL or 'noreply@toolcalibration.com',
                    [supervisor.email],
                    fail_silently=False,
                )
                self.stdout.write(f'   ✅ Email envoyé à {supervisor.email}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Erreur email pour {supervisor.email}: {str(e)}'))