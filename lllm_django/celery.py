from __future__ import absolute_import, unicode_literals
import os

from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lllm_django.settings')

app = Celery('lllm_django')
app.conf.enable_utc = False
app.conf.update(timezone='Asia/Kolkata',  enable_utc=False, )
app.config_from_object(settings, namespace='CELERY')

app.conf.update(
    broker_url='redis://localhost:6379/0',  # Redis as broker
    result_backend='redis://localhost:6379/0',  # Redis as result backend
)


# beat setting
# ← Add this:
app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'

app.autodiscover_tasks()
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

