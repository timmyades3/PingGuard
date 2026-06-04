import logging
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Incident, Settings

logger = logging.getLogger(__name__)

# The follow-up notification interval (currently hardcoded to 1 hour, can be made configurable later)
# NOTIFICATION_INTERVAL = timedelta(hours=1)

def recipient_email(user):
    settings_obj = Settings.objects.filter(user=user).first()
    if settings_obj and settings_obj.notification_email:
        return settings_obj.notification_email
    return user.email

def send_down_email(user, target_type, target_obj, error_message):
    subject = f"[{target_type}] Alert: {target_obj} is DOWN"
    message = f"Hello {user.username},\n\nYour {target_type} monitoring target '{target_obj}' is currently DOWN.\n\nError: {error_message}\n\nTime: {timezone.now()}"
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@ipms.local',
            [recipient_email(user)],
            fail_silently=True,
        )
        logger.info(f"Sent DOWN email to {recipient_email(user)} for {target_type} {target_obj}")
    except Exception as e:
        logger.error(f"Failed to send DOWN email to {recipient_email(user)  }: {e}")

def send_still_down_email(user, target_type, target_obj, incident):
    subject = f"[{target_type}] Reminder: {target_obj} is STILL DOWN"
    downtime_duration = timezone.now() - incident.started_at
    message = f"Hello {user.username},\n\nYour {target_type} monitoring target '{target_obj}' has been DOWN for {str(downtime_duration).split('.')[0]}.\n\nTime: {timezone.now()}"
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@ipms.local',
            [recipient_email(user)],
            fail_silently=True,
        )
        logger.info(f"Sent STILL DOWN email to {recipient_email(user)} for {target_type} {target_obj}")
    except Exception as e:
        logger.error(f"Failed to send STILL DOWN email to {recipient_email(user)}: {e}")

def send_up_email(user, target_type, target_obj, incident):
    subject = f"[{target_type}] Resolved: {target_obj} is UP"
    downtime_duration = incident.resolved_at - incident.started_at
    message = f"Hello {user.username},\n\nGood news! Your {target_type} monitoring target '{target_obj}' is back UP.\nIt was down for {str(downtime_duration).split('.')[0]}.\n\nTime: {timezone.now()}"
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@ipms.local',
            [recipient_email(user) ],
            fail_silently=True,
        )
        logger.info(f"Sent UP email to {recipient_email(user)} for {target_type} {target_obj}")
    except Exception as e:
        logger.error(f"Failed to send UP email to {recipient_email(user)}: {e}")

def process_check_result(user, target_type, target_obj, status, error_message=""):
    """
    Evaluates the check result and manages the Incident lifecycle and notifications.
    """
    now = timezone.now()
    
    # Identify the appropriate kwargs based on target type
    kwargs = {'user': user, 'target_type': target_type, 'status': 'OPEN'}
    if target_type == 'IP':
        kwargs['ip_address'] = target_obj
    else:
        kwargs['endpoint'] = target_obj

    if status == 'DOWN':
        # Look for an OPEN incident
        incident = Incident.objects.filter(**kwargs).first()
        
        if not incident:
            # Create a new Incident
            kwargs['last_notification_sent_at'] = now
            incident = Incident.objects.create(**kwargs)
            send_down_email(user, target_type, target_obj, error_message)
        else:
            # Incident already open, check if we need to send follow-up
            setting = Settings.objects.filter(user=user).first()
            
            if incident.last_notification_sent_at and (now - incident.last_notification_sent_at) >= timedelta(minutes=setting.notification_interval_minutes):
                send_still_down_email(user, target_type, target_obj, incident)
                incident.last_notification_sent_at = now
                incident.save()

    elif status == 'UP':
        # Look for an OPEN incident and resolve it
        incident = Incident.objects.filter(**kwargs).first()
        if incident:
            incident.status = 'RESOLVED'
            incident.resolved_at = now
            incident.save()
            send_up_email(user, target_type, target_obj, incident)
