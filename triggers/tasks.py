from celery import shared_task
from django.dispatch import Signal, receiver

from triggers.models import Event
from triggers.signals import TRACE_ID_CONTEXT_KEY


@receiver(Event.fired)
def on_event_fired(sender, signal: Signal, event: Event, user_pk, **kwargs):
    handle_event.apply_async(
        args=(event.pk, user_pk),
        kwargs=kwargs,
        countdown=event.delay.total_seconds(),
    )


@shared_task
def handle_event(event_pk, user_pk, **context):
    event: Event = Event.objects.get(pk=event_pk)
    trace_id = context.pop(TRACE_ID_CONTEXT_KEY, "")
    event.handle(user_pk, trace_id=trace_id, **context)
