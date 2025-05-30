#!/usr/bin/env python
"""
Debug script to directly test Temporal workflow execution.

This script bypasses the Django signal system and directly invokes the Temporal workflow.
"""

import asyncio
from datetime import timedelta
import logging
import os
import sys

from asgiref.sync import sync_to_async
import django
from temporalio.common import RetryPolicy


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

# Import Django models and Temporal client
from django.contrib.auth import get_user_model

from triggers import settings as triggers_settings
from triggers.models import Event, Trigger
from triggers.temporal.client import get_temporal_client


async def main():
    """Test Temporal workflow execution directly."""
    User = get_user_model()

    # Log configuration settings
    logger.info("Django-Triggers Temporal Configuration:")
    logger.info(f"TRIGGERS_USE_TEMPORAL: {triggers_settings.TRIGGERS_USE_TEMPORAL}")
    logger.info(f"TEMPORAL_HOST: {triggers_settings.TEMPORAL_HOST}")
    logger.info(f"TEMPORAL_NAMESPACE: {triggers_settings.TEMPORAL_NAMESPACE}")
    logger.info(f"TEMPORAL_TASK_QUEUE: {triggers_settings.TEMPORAL_TASK_QUEUE}")

    # Get references to database objects
    @sync_to_async
    def get_objects():
        first_user = User.objects.first()
        first_trigger = Trigger.objects.first()
        first_event = Event.objects.first()
        return first_user, first_trigger, first_event

    user, trigger, event = await get_objects()
    if not all([user, trigger, event]):
        logger.error("Could not find user, trigger, or event in database")
        return 1

    logger.info(f"Using user: {user.username} (ID: {user.id})")
    logger.info(f"Using trigger: {trigger.name} (ID: {trigger.id})")
    logger.info(f"Using event: {type(event).__name__} (ID: {event.id})")

    # Connect to Temporal
    try:
        logger.info(
            f"Connecting to Temporal server at {triggers_settings.TEMPORAL_HOST}"
        )
        client = await get_temporal_client()
        logger.info("Successfully connected to Temporal server")
    except Exception as e:
        logger.exception(f"Failed to connect to Temporal server: {str(e)}")
        return 1

    # Create workflow ID same as would be created by the hooks
    workflow_id = f"trigger-{trigger.id}-{user.id}-{event.id}"
    logger.info(f"Using workflow ID: {workflow_id}")

    # Execute workflow directly
    try:
        logger.info("Starting Temporal workflow...")

        # Context data that would normally be passed from the event
        context_data = {"test_param": "debug_test"}

        # Create a proper RetryPolicy object
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=5,
        )

        # Start the workflow
        handle = await client.start_workflow(
            "trigger_workflow",  # Must match the name in @workflow.defn
            args=[trigger.id, user.id, context_data],
            id=workflow_id,
            task_queue=triggers_settings.TEMPORAL_TASK_QUEUE,
            retry_policy=retry_policy,
        )

        logger.info(f"Workflow started with ID: {workflow_id}")

        # Wait for workflow execution (with timeout)
        try:
            logger.info("Waiting for workflow result (timeout: 5s)...")
            result = await asyncio.wait_for(handle.result(), timeout=5)
            logger.info(f"Workflow completed with result: {result}")
        except asyncio.TimeoutError:
            logger.warning("Workflow is still running after timeout")
            logger.info(
                f"You can check its status in the Temporal UI: {triggers_settings.TEMPORAL_HOST}"
            )

    except Exception as e:
        if "already started" in str(e).lower():
            logger.warning(f"Workflow with ID {workflow_id} already exists")
            logger.info("Trying to get existing workflow handle...")

            try:
                handle = client.get_workflow_handle(workflow_id)
                logger.info(f"Got handle for existing workflow: {workflow_id}")

                # Check workflow status
                try:
                    status = await handle.describe()
                    logger.info(f"Workflow status: {status.status}")
                except Exception as describe_error:
                    logger.exception(f"Error getting workflow status: {describe_error}")
            except Exception as handle_error:
                logger.exception(f"Error getting workflow handle: {handle_error}")
        else:
            logger.exception(f"Error starting workflow: {e}")

    logger.info("Test complete!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
