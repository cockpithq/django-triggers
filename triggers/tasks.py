from celery import shared_task
from django.dispatch import Signal, receiver

from triggers.models import Event


@receiver(Event.fired)
def on_event_fired(sender, signal: Signal, event: Event, user_pk, run_id: str, **kwargs):
    handle_event.apply_async(
        args=(event.pk, user_pk),
        kwargs={"run_id": run_id, **kwargs},
        countdown=event.delay.total_seconds(),
    )


@shared_task
def handle_event(event_pk, user_pk, run_id: str = "", **context):
    event: Event = Event.objects.get(pk=event_pk)
    event.handle(user_pk, run_id=run_id, **context)
