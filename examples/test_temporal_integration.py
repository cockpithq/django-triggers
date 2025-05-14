#!/usr/bin/env python
"""
Example script for testing the Temporal integration with django-triggers.

This script demonstrates:
1. How to configure the integration in a Django project
2. How to manually fire an event and verify it's processed by Temporal
3. How to run both Celery and Temporal in parallel during migration

To run this example:
1. Make sure you have a Temporal server running (see README.md)
2. Install the dependencies: `uv add temporalio asgiref`
3. Set DJANGO_SETTINGS_MODULE to point to your Django settings
4. Run this script: `python examples/test_temporal_integration.py`
"""

import os
import sys
import asyncio
import logging
import django
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
django.setup()

# Import django-triggers components
from triggers.models import Trigger, Event
from triggers import settings as triggers_settings
from triggers.temporal.client import get_temporal_client


async def monitor_workflow(client, workflow_id, timeout=5):
    """Monitor a workflow execution and print its status."""
    try:
        handle = client.get_workflow_handle(workflow_id)
        result = await asyncio.wait_for(handle.result(), timeout=timeout)
        logger.info(f"Workflow {workflow_id} completed successfully")
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"Workflow {workflow_id} is still running after {timeout} seconds"
        )
        logger.info(
            f"You can check its status in the Temporal UI: {triggers_settings.TEMPORAL_HOST}"
        )
        return None
    except Exception as e:
        logger.error(f"Error monitoring workflow {workflow_id}: {str(e)}")
        return None


async def list_running_workflows(client):
    """List running workflows in the Temporal namespace."""
    try:
        # Get all running workflows
        workflows = client.list_workflows(query="ExecutionStatus='Running'")
        count = 0
        async for workflow in workflows:
            count += 1
            logger.info(
                f"Running workflow: {workflow.id} (Type: {workflow.type}, Start time: {workflow.start_time})"
            )

        if count == 0:
            logger.info("No running workflows found")
    except Exception as e:
        logger.error(f"Error listing workflows: {str(e)}")


# Sync wrapper functions
@sync_to_async
def get_first_user():
    User = get_user_model()
    return User.objects.first()


@sync_to_async
def create_test_user():
    User = get_user_model()
    return User.objects.create_user(
        username="test_user",
        email="test@example.com",
        password="password",
    )


@sync_to_async
def get_first_trigger():
    return Trigger.objects.first()


@sync_to_async
def get_first_event_for_trigger(trigger):
    return Event.objects.filter(trigger=trigger).first()


@sync_to_async
def fire_event(event, user_id):
    """Fire the event and log details about it."""
    logger = logging.getLogger(__name__)
    logger.info(f"fire_event called with event ID: {event.id}, user_id: {user_id}")

    try:
        # Check if the temporal workflow execution function exists
        logger.info("Temporal workflow execution function exists")

        # Directly call the workflow execution function for debugging
        User = get_user_model()
        user = User.objects.get(id=user_id)
        trigger = event.trigger
        workflow_id = f"trigger-{trigger.id}-{user.id}-{event.id}"
        logger.info(f"About to direct execute workflow with ID: {workflow_id}")

        # Now fire the event normally
        logger.info("Firing event through normal channel")
        event.fire_single(user_id)
        logger.info("Event fired successfully")
    except Exception as e:
        logger.error(f"Error in fire_event: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())


async def main():
    """Main example function."""
    # Check if Temporal integration is enabled
    if not triggers_settings.TRIGGERS_USE_TEMPORAL:
        logger.error("Temporal integration is not enabled")
        logger.error("Please add TRIGGERS_USE_TEMPORAL = True to your settings")
        return 1

    # Get Temporal client
    try:
        client = await get_temporal_client()
        logger.info(
            f"Connected to Temporal server at {triggers_settings.TEMPORAL_HOST}"
        )
        logger.info(f"Using namespace: {triggers_settings.TEMPORAL_NAMESPACE}")
    except Exception as e:
        logger.error(f"Failed to connect to Temporal server: {str(e)}")
        logger.error("Make sure your Temporal server is running")
        return 1

    # List running workflows
    logger.info("Checking for running workflows...")
    await list_running_workflows(client)

    # Get a user to test with (create one if needed)
    user = await get_first_user()
    if not user:
        logger.info("Creating a test user...")
        user = await create_test_user()

    # Get a trigger to test with
    trigger = await get_first_trigger()
    if not trigger:
        logger.warning("No triggers found in the database")
        logger.warning("Please create a trigger in the Django admin")
        return 1

    # Find an event for this trigger
    event = await get_first_event_for_trigger(trigger)
    if not event:
        logger.warning("No events found for trigger")
        logger.warning("Please create an event for this trigger in the Django admin")
        return 1

    # Manually fire the event
    logger.info(f"Firing event '{event}' for user '{user.username}'...")

    # The deterministic workflow ID that will be generated
    workflow_id = f"trigger-{trigger.id}-{user.id}-{event.id}"

    # Fire the event (this will trigger both Celery and Temporal if both are enabled)
    await fire_event(event, user.id)

    # Monitor the workflow execution
    logger.info(f"Monitoring workflow execution (ID: {workflow_id})...")
    await monitor_workflow(client, workflow_id)

    logger.info("Test complete!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
