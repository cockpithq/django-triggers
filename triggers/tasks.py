from celery import shared_task
from django.dispatch import Signal, receiver

from triggers.models import RUN_ID_CONTEXT_KEY, Event


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
    # Extract run_id from context (either from RUN_ID_CONTEXT_KEY or 'run_id' key)
    run_id = context.pop(RUN_ID_CONTEXT_KEY, context.pop('run_id', ''))
    event.handle(user_pk, run_id=run_id, **context)
