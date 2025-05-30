#!/usr/bin/env python
"""
Standalone script for running a Temporal worker for django-triggers.

This script can be used to run a Temporal worker process outside
of the Django management command system, for example in production
environments where you want to deploy the worker separately.

Usage:
    python worker.py --settings=myproject.settings
"""

import argparse
import asyncio
import logging
import os
import sys

import django


def setup_django(settings_module):
    """Set up Django with the specified settings module."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    django.setup()


async def run_worker(task_queue=None, debug=False):
    """
    Run the Temporal worker for django-triggers.

    Args:
        task_queue: Temporal task queue to poll (overrides settings)
        debug: Whether to enable debug logging
    """
    # Import here after Django is set up
    from temporalio.worker import Worker

    from triggers import settings as triggers_settings
    from triggers.temporal.client import get_temporal_client
    from triggers.temporal.workflows import (
        TriggerWorkflow,
        evaluate_condition,
        fetch_trigger_definition,
        log_activity,
        perform_action,
    )

    # Check if Temporal integration is enabled
    if not triggers_settings.TRIGGERS_USE_TEMPORAL:
        raise ValueError(
            "Temporal integration is disabled. Set TRIGGERS_USE_TEMPORAL=True "
            "in your settings to enable it."
        )

    # Set up logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Use the provided task queue or get from settings
    task_queue = task_queue or triggers_settings.TEMPORAL_TASK_QUEUE

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Temporal worker on task queue: {task_queue}")
    logger.info(f"Using Temporal server: {triggers_settings.TEMPORAL_HOST}")
    logger.info(f"Using namespace: {triggers_settings.TEMPORAL_NAMESPACE}")

    # Initialize Temporal client and worker
    client = await get_temporal_client()
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

    logger.info("Connected to Temporal server")
    logger.info("Press Ctrl+C to stop the worker")

    # Start the worker
    await worker.run()


def main():
    """Parse arguments and run the worker."""
    parser = argparse.ArgumentParser(
        description="Run a Temporal worker for django-triggers"
    )
    parser.add_argument(
        "--settings",
        required=True,
        help="Django settings module (e.g., 'myproject.settings')",
    )
    parser.add_argument(
        "--task-queue",
        help="Temporal task queue to poll (overrides settings value)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Set up Django
    setup_django(args.settings)

    # Run the worker
    try:
        asyncio.run(run_worker(args.task_queue, args.debug))
    except KeyboardInterrupt:
        print("\nStopping worker...")
    except Exception as e:
        print(f"\nError: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
