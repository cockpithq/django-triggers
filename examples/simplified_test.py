#!/usr/bin/env python
"""
Simplified test for Temporal integration without using django-triggers.
This script creates a basic workflow and tests if the Temporal server is working correctly.

To run this script:
1. Make sure you have a Temporal server running
2. Run this script: `python examples/simplified_test.py`
"""

import asyncio
from datetime import timedelta
import logging
import sys
import uuid

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Define a simple activity
@activity.defn
async def say_hello(name: str) -> str:
    logger.info(f"Activity executed with name: {name}")
    return f"Hello, {name}!"


# Define a simple workflow
@workflow.defn
class SimpleWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        workflow_result = await workflow.execute_activity(
            say_hello, name, schedule_to_close_timeout=timedelta(seconds=60)
        )
        return workflow_result


async def run_simplified_test():
    """Test if Temporal server is working by running a simple workflow."""

    try:
        # Connect to Temporal server
        logger.info("Connecting to Temporal server at localhost:7233")
        client = await Client.connect("localhost:7233")
        logger.info("Connected to Temporal server")

        # Create task queue name
        task_queue = "simplified-test-queue"

        # Generate a unique workflow ID
        workflow_id = f"simplified-test-workflow-{uuid.uuid4()}"

        # Run worker in the background
        logger.info(f"Starting worker on task queue: {task_queue}")
        async with Worker(
            client=client,
            task_queue=task_queue,
            workflows=[SimpleWorkflow],
            activities=[say_hello],
        ):
            # Execute workflow
            logger.info(f"Executing workflow with ID: {workflow_id}")
            result = await client.execute_workflow(
                SimpleWorkflow.run,
                "Temporal",
                id=workflow_id,
                task_queue=task_queue,
            )
            logger.info(f"Workflow result: {result}")
            return True
    except Exception as e:
        logger.error(f"Error running simplified test: {e}")
        return False


async def main():
    """Main function to run the test."""
    success = await run_simplified_test()
    if success:
        logger.info(
            "Simplified test completed successfully. Temporal server is working correctly."
        )
    else:
        logger.error(
            "Simplified test failed. There might be issues with the Temporal server or configuration."
        )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
