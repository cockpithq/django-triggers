"""
Django-Temporal integration hooks for trigger events.

This module connects Django signal handlers with Temporal workflow execution.
"""

from datetime import timedelta
import logging
from typing import Any

from asgiref.sync import async_to_sync
from django.dispatch import Signal, receiver
from django.utils.module_loading import import_string
from temporalio.common import RetryPolicy

from triggers import settings as triggers_settings
from triggers.models import Event
from triggers.temporal.client import get_temporal_client


logger = logging.getLogger(__name__)


def start_trigger_workflow(event: Event, user_pk: Any, **kwargs):
    """
    Start a Temporal workflow for a triggered event.

    This function creates a deterministic workflow ID based on the event
    and user information to ensure idempotent workflow execution (preventing
    duplicate executions of the same logical event).

    Args:
        event: The Event instance that was fired
        user_pk: Primary key of the user the event is for
        **kwargs: Additional context data from the event
    """
    if not triggers_settings.TRIGGERS_USE_TEMPORAL:
        logger.debug(
            "Temporal integration is disabled (TRIGGERS_USE_TEMPORAL=False). "
            "Skipping workflow execution for event %d (trigger: %s, user: %s).",
            event.pk,
            event.trigger.name,
            user_pk,
        )
        return

    # We need to use async_to_sync since Django signals are synchronous
    # but Temporal client is async
    async def _async_start_workflow():
        try:
            client = await get_temporal_client()

            # Create a deterministic workflow ID for deduplication
            workflow_id = f"trigger-{event.trigger_id}-{user_pk}-{event.pk}"

            logger.info(
                "Starting Temporal workflow for event %d (trigger: %s, user: %s)",
                event.pk,
                event.trigger.name,
                user_pk,
            )

            # Create proper RetryPolicy object
            retry_policy = RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=5,
            )

            # Start the workflow with the appropriate arguments
            await client.start_workflow(
                "trigger_workflow",  # Must match the name in @workflow.defn
                args=[event.trigger_id, user_pk, kwargs],
                id=workflow_id,
                task_queue=triggers_settings.TEMPORAL_TASK_QUEUE,
                retry_policy=retry_policy,  # Use the proper RetryPolicy object
            )

            logger.debug(
                "Successfully started Temporal workflow %s for event %d",
                workflow_id,
                event.pk,
            )

        except Exception as e:
            logger.exception(
                "Failed to start Temporal workflow for event %d: %s", event.pk, str(e)
            )
            raise

    # Convert the async function to a sync one and execute it
    async_to_sync(_async_start_workflow)()


# Custom signal handler registry to allow dynamic replacement
# of the default signal handler
_custom_handler = None


def set_custom_event_handler(handler_path=None):
    """
    Set a custom event handler function to be used instead of the default.

    This allows projects to customize the event handling without modifying
    the django-triggers codebase directly.

    Args:
        handler_path: Dotted path to a function that will handle Event.fired signals.
                     The function should accept the same arguments as on_event_fired.
                     If None, the default handler will be used.
    """
    global _custom_handler
    if handler_path:
        _custom_handler = import_string(handler_path)
    else:
        _custom_handler = None


# Connect this to the Django Event.fired signal
@receiver(Event.fired)
def on_event_fired(sender, signal: Signal, event: Event, user_pk, **kwargs):
    """
    Signal handler for Event.fired signals.

    This replaces or supplements the existing Celery-based handler
    in triggers.tasks.on_event_fired.

    Args:
        sender: The sender of the signal (Event class)
        signal: The signal instance
        event: The Event instance that was fired
        user_pk: Primary key of the user the event is for
        **kwargs: Additional context data for the event
    """
    # Use custom handler if provided
    if _custom_handler:
        return _custom_handler(sender, signal, event, user_pk, **kwargs)

    # Determine if we should use Temporal based on settings
    if triggers_settings.TRIGGERS_USE_TEMPORAL:
        # Start a Temporal workflow for this event
        start_trigger_workflow(event, user_pk, **kwargs)
    else:
        # Let the default Celery handler process the event
        # The signal will reach the handlers in triggers.tasks as well
        logger.debug(
            "Temporal integration is disabled. Using default Celery handler for "
            "event %d (trigger: %s, user: %s).",
            event.pk,
            event.trigger.name,
            user_pk,
        )
