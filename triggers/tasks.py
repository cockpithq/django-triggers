from celery import shared_task
from django.dispatch import Signal, receiver

from triggers.models import Event, log_trigger_event


@receiver(Event.fired)
def on_event_fired(sender, signal: Signal, event: Event, user_pk, **kwargs):
    # Extract run_id from kwargs
    run_id = kwargs.pop("_run_id", None)
    
    log_trigger_event(
        entity=event,
        entity_type="event",
        stage="task_created",
        details={
            "user_pk": user_pk,
            "countdown": event.delay.total_seconds(),
            "kwargs": str(kwargs)
        },
        run_id=run_id
    )
    
    # Add run_id back to kwargs for Celery task
    kwargs["_run_id"] = run_id
    
    handle_event.apply_async(
        args=(event.pk, user_pk),
        kwargs=kwargs,
        countdown=event.delay.total_seconds(),
    )


@shared_task
def handle_event(event_pk, user_pk, **context):
    try:
        # Extract run_id from context
        run_id = context.pop("_run_id", None)
        
        event: Event = Event.objects.get(pk=event_pk)
        log_trigger_event(
            entity=event,
            entity_type="event",
            stage="handle_start",
            details={
                "event_pk": event_pk,
                "user_pk": user_pk,
                "context": str(context)
            },
            run_id=run_id
        )
        
        # Add run_id back to context
        context["_run_id"] = run_id
        
        event.handle(user_pk, **context)
    except Exception as e:
        # Log the error
        if "event" in locals():
            log_trigger_event(
                entity=event,
                entity_type="event",
                stage="handle_start",
                result=False,
                details={"error": str(e)},
                run_id=run_id
            )
        raise
