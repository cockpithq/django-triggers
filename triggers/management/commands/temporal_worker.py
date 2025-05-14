"""
Django management command to run a Temporal worker for django-triggers.
"""

import asyncio
import logging

from django.core.management.base import BaseCommand, CommandError
from temporalio.worker import Worker

from triggers import settings as triggers_settings
from triggers.temporal.client import get_temporal_client
from triggers.temporal.workflows import (
    TriggerWorkflow,
    fetch_trigger_definition,
    evaluate_condition,
    perform_action,
    log_activity,
)


class Command(BaseCommand):
    """
    Management command to run a Temporal worker for django-triggers.

    This worker processes Temporal workflows and activities for the trigger system.
    """

    help = "Run the Temporal worker for django-triggers workflows and activities"

    def add_arguments(self, parser):
        parser.add_argument(
            "--task-queue",
            type=str,
            default=triggers_settings.TEMPORAL_TASK_QUEUE,
            help=f"Temporal task queue to poll (default: '{triggers_settings.TEMPORAL_TASK_QUEUE}')",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug logging",
        )

    def handle(self, *args, **options):
        """
        Run the Temporal worker.

        This is the main entry point for the management command.
        """
        # Check if Temporal integration is enabled
        if not triggers_settings.TRIGGERS_USE_TEMPORAL:
            raise CommandError(
                "Temporal integration is disabled. Set TRIGGERS_USE_TEMPORAL=True "
                "in your settings to enable it."
            )

        # Set up logging
        log_level = logging.DEBUG if options["debug"] else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Get task queue from options
        task_queue = options["task_queue"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Temporal worker for django-triggers on task queue '{task_queue}'"
            )
        )
        self.stdout.write(
            f"Using Temporal server at: {triggers_settings.TEMPORAL_HOST}"
        )
        self.stdout.write(f"Using namespace: {triggers_settings.TEMPORAL_NAMESPACE}")

        # Run the worker
        try:
            asyncio.run(self._run_worker(task_queue))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nStopping worker..."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error running worker: {str(e)}"))
            raise

    async def _run_worker(self, task_queue: str):
        """
        Run the Temporal worker asynchronously.

        Args:
            task_queue: The Temporal task queue to poll
        """
        client = await get_temporal_client()

        # Create a worker that polls the specified task queue
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

        # Log info about the worker
        logger = logging.getLogger(__name__)
        logger.info(
            f"Connected to Temporal server at {triggers_settings.TEMPORAL_HOST}"
        )
        logger.info(f"Using namespace: {client.namespace}")
        logger.info(f"Worker registered with task queue: {task_queue}")
        logger.info("Press Ctrl+C to stop the worker")

        # Run the worker (this is a blocking call)
        await worker.run()
