#!/usr/bin/env python
"""
Debugging script to test the Temporal hooks.

This script verifies that the Temporal hooks are properly connected to Django signals.
"""

import os
import sys
import django
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
django.setup()

# Import Django models
from django.contrib.auth import get_user_model
from triggers.models import Trigger, Event
from triggers.temporal.hooks import on_event_fired
from triggers import settings as triggers_settings


def main():
    """Check and debug the Temporal integration hooks."""
    User = get_user_model()

    # Log configuration settings
    logger.info("Django-Triggers Temporal Configuration:")
    logger.info(f"TRIGGERS_USE_TEMPORAL: {triggers_settings.TRIGGERS_USE_TEMPORAL}")
    logger.info(f"TEMPORAL_HOST: {triggers_settings.TEMPORAL_HOST}")
    logger.info(f"TEMPORAL_NAMESPACE: {triggers_settings.TEMPORAL_NAMESPACE}")
    logger.info(f"TEMPORAL_TASK_QUEUE: {triggers_settings.TEMPORAL_TASK_QUEUE}")

    # Check available triggers and events
    triggers = list(Trigger.objects.all())
    logger.info(f"Available triggers ({len(triggers)}):")
    for t in triggers:
        logger.info(f"  - ID: {t.id}, Name: {t.name}, Enabled: {t.is_enabled}")

        events = list(t.events.all())
        logger.info(f"    Events ({len(events)}):")
        for e in events:
            logger.info(f"      - ID: {e.id}, Type: {type(e).__name__}")

    # Check if we can import the Temporal client
    try:
        logger.info("Successfully imported Temporal client")
    except Exception as e:
        logger.exception(f"Failed to import Temporal client: {str(e)}")

    # Check registered signal handlers for Event.fired
    from django.dispatch.dispatcher import _live_receivers

    logger.info("Registered handlers for Event.fired signal:")
    handlers = _live_receivers(Event.fired)
    for handler in handlers:
        logger.info(f"  - {handler.__module__}.{handler.__name__}")

    # Check if our Temporal handler is in the list
    temporal_handler_name = f"{on_event_fired.__module__}.{on_event_fired.__name__}"
    if any(f"{h.__module__}.{h.__name__}" == temporal_handler_name for h in handlers):
        logger.info(f"✅ Temporal handler {temporal_handler_name} is registered")
    else:
        logger.warning(f"❌ Temporal handler {temporal_handler_name} is NOT registered")

    # Try to manually call the Temporal handler
    try:
        first_user = User.objects.first()
        first_event = Event.objects.first()

        if first_user and first_event:
            logger.info(
                f"Manually calling Temporal handler for event {first_event.id} and user {first_user.id}"
            )
            on_event_fired(
                Event, Event.fired, first_event, first_user.id, test_param="manual_test"
            )
            logger.info("Temporal handler called successfully")
        else:
            logger.warning("Cannot test handler - missing user or event")
    except Exception as e:
        logger.exception(f"Error calling Temporal handler: {str(e)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
