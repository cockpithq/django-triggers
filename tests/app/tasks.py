from celery import shared_task
from django.contrib.auth.models import User

from tests.app.models import ClockEvent


@shared_task
def clock():
    clock_event: ClockEvent
    for clock_event in ClockEvent.objects.all():
        clock_event.fire(User.objects.all())
