import os
from celery import Celery
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'hourly-aggregate-and-cleanup': {
        'task': 'monitoring.tasks.hourly_aggregate_and_cleanup',
        'schedule': timedelta(hours=1),
    },
    'daily-aggregate-and-cleanup': {
        'task': 'monitoring.tasks.daily_aggregate_and_cleanup',
        'schedule': timedelta(hours=24),
    },
}


