#!/usr/bin/env python
"""
Simple script to run a Temporal worker for testing the django-triggers integration.

This script starts a Temporal worker that processes workflows and activities
for the django-triggers system.

To run this script:
1. Make sure you have a Temporal server running (see README.md)
2. Install the dependencies: `uv add temporalio asgiref`
3. Set DJANGO_SETTINGS_MODULE to point to your Django settings
4. Run this script: `python examples/run_temporal_worker.py`
"""

import asyncio
import logging
import os
import sys

import django


# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Enable detailed logging for specific modules
logging.getLogger("triggers").setLevel(logging.INFO)
logging.getLogger("triggers.temporal").setLevel(logging.INFO)
logging.getLogger("examples").setLevel(logging.INFO)
logging.getLogger("temporalio").setLevel(
    logging.WARNING
)  # Only show warnings from the Temporal SDK

logger = logging.getLogger(__name__)

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
django.setup()

# Now import django-triggers components
try:
    from temporalio.worker import Worker

    from triggers import settings as triggers_settings
    from triggers.temporal.client import get_temporal_client

    # Import from isolated workflow that doesn't have Django imports
    from triggers.temporal.isolated_workflows import TriggerWorkflow

    # Import activities from the Django-aware module
    from triggers.temporal.workflows import (
        evaluate_condition,
        fetch_trigger_definition,
        log_activity,
        perform_action,
    )
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    sys.exit(1)


async def run_worker(task_queue=None):
    """Run a Temporal worker for django-triggers."""
    # Check if Temporal integration is enabled
    if not triggers_settings.TRIGGERS_USE_TEMPORAL:
        logger.error("❌ Temporal integration is not enabled")
        logger.error("Please add TRIGGERS_USE_TEMPORAL = True to your settings")
        return 1

    # Use the configured task queue or override
    task_queue = task_queue or triggers_settings.TEMPORAL_TASK_QUEUE

    logger.info(f"🚀 Starting Temporal worker on task queue: {task_queue}")
    logger.info(f"🔌 Using Temporal server: {triggers_settings.TEMPORAL_HOST}")
    logger.info(f"🔍 Using namespace: {triggers_settings.TEMPORAL_NAMESPACE}")

    try:
        # Initialize Temporal client
        client = await get_temporal_client()

        logger.info("✅ Successfully connected to Temporal server")
        logger.info(f"🔍 Namespace: {client.namespace}")

        # List registered workflows and activities
        logger.info("📋 Registering workflows:")
        for workflow in [TriggerWorkflow]:
            workflow_name = getattr(
                workflow, "__temporal_workflow_definition__", {}
            ).get("name", "unknown")
            logger.info(f" ↪ {workflow.__name__} (name: {workflow_name})")

        logger.info("📋 Registering activities:")
        for activity in [
            fetch_trigger_definition,
            evaluate_condition,
            perform_action,
            log_activity,
        ]:
            activity_name = getattr(
                activity, "__temporal_activity_definition__", {}
            ).get("name", "unknown")
            logger.info(f" ↪ {activity.__name__} (name: {activity_name})")

        # Create a worker
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[TriggerWorkflow],
            activities=[
                fetch_trigger_definition,
                evaluate_condition,
                perform_action,
                log_activity,
            ],
        )

        logger.info("✅ Worker created successfully")
        logger.info("⚙️ Worker is running. Press Ctrl+C to stop.")
        logger.info(
            "🌐 Check Temporal UI at http://localhost:8233 to monitor workflows"
        )

        # Run the worker (this is a blocking call)
        await worker.run()

    except KeyboardInterrupt:
        logger.info("👋 Worker stopped by user")
        return 0
    except Exception as e:
        logger.error(f"❌ Error running worker: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run a Temporal worker for django-triggers"
    )
    parser.add_argument(
        "--task-queue",
        help=f"Temporal task queue to poll (default: {triggers_settings.TEMPORAL_TASK_QUEUE})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger("triggers").setLevel(logging.DEBUG)
        logging.getLogger("triggers.temporal").setLevel(logging.DEBUG)
        logging.getLogger("examples").setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔍 Debug logging enabled")

    # Run the worker
    exit_code = asyncio.run(run_worker(args.task_queue))
    sys.exit(exit_code)
