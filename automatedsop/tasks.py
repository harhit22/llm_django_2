
import os

# Ensure the settings are properly configured
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lllm_django.settings")
from celery import shared_task

@shared_task
def run_no_bot_ask_gemini_api():
    from automatedsop.views import NoBotAskGeminiAPIDustbinStatus
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    request = factory.post('/dustbin-status-endpoint/')  # use actual URL if needed
    view = NoBotAskGeminiAPIDustbinStatus.as_view()
    response = view(request)
    return response.data

@shared_task
def run_no_bot_ask_gemini_api_field_executive():
    from automatedsop.views import NoBotAskGeminiAPIView
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    request = factory.post('/sop1/')  # use actual URL if needed
    view = NoBotAskGeminiAPIView.as_view()
    response = view(request)
    return response.data

@shared_task
def run_no_bot_ask_gemini_api_transport_executive():
    from automatedsop.views import NoBotAskGeminiAPIViewTransportExec
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    request = factory.post('/sop2/')  # use actual URL if needed
    view = NoBotAskGeminiAPIViewTransportExec.as_view()
    response = view(request)
    return response.data


from celery import Celery
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from datetime import timedelta

def schedule_task():
    schedule, created = IntervalSchedule.objects.get_or_create(
        every=1, period=IntervalSchedule.DAYS
    )
    task = PeriodicTask.objects.create(
        interval=schedule,
        name="Run Dustbin Status Task",
        task="lllm_django.tasks.run_no_bot_ask_gemini_api",
        expires=timedelta(days=1),
        start_time="2025-05-07 9:35:00",  # The date to start from
    )
