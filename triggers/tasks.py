from celery import shared_task
from django.dispatch import Signal, receiver

from triggers.models import Event


@receiver(Event.fired)
def on_event_fired(sender, signal: Signal, event: Event, user_pk, **kwargs):
    handle_event.delay(event.pk, user_pk, **kwargs)


@shared_task
def handle_event(event_pk, user_pk, **context):
    event: Event = Event.objects.get(pk=event_pk)
    event.handle(user_pk, **context)
