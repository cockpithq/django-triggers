#!/usr/bin/env python
"""
Test script to simulate a medical form submission for the django-triggers Temporal integration.

This script:
1. Creates a test user if needed
2. Uses an existing trigger from the database
3. Submits form data to trigger the workflow

Usage:
    python examples/test_form_submit.py
"""

import os
import sys
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
import django

django.setup()

from django.contrib.auth.models import User
from asgiref.sync import sync_to_async
from triggers.models import Trigger, Event


class BMIData:
    """Simple class to hold BMI data for our test."""

    def __init__(self, height_cm, weight_kg, user_id):
        self.height_cm = height_cm
        self.weight_kg = weight_kg
        self.user_id = user_id
        # Calculate BMI
        self.bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)


async def setup_test():
    """Set up the test data (user and trigger)."""
    # Get or create a test user
    try:
        user = await sync_to_async(User.objects.get)(username="testuser")
        logger.info(f"Using existing user: {user.username}")
    except User.DoesNotExist:
        user = await sync_to_async(User.objects.create_user)(
            username="testuser", email="test@example.com", password="password"
        )
        logger.info(f"Created new user: {user.username}")

    # Get all events in the database
    events = await sync_to_async(list)(Event.objects.all())
    if not events:
        logger.error(
            "No events found in the database. Please create at least one in the admin interface."
        )
        return None, None

    # Use the first event available
    event = events[0]
    logger.info(f"Using event: {event}")

    # Get all triggers in the database
    triggers = await sync_to_async(list)(Trigger.objects.all())
    if not triggers:
        logger.error(
            "No triggers found in the database. Please create at least one in the admin interface."
        )
        return user, None

    # Use the first trigger available
    trigger = triggers[0]
    logger.info(f"Using trigger: {trigger.name}")

    # Check if the trigger is enabled
    if not trigger.is_enabled:
        logger.warning(f"Trigger '{trigger.name}' is not enabled - enabling it")
        trigger.is_enabled = True
        await sync_to_async(trigger.save)()

    # Make sure the event is associated with the trigger
    trigger_events = await sync_to_async(list)(trigger.events.all())
    if event not in trigger_events:
        logger.warning(
            f"Event '{event}' not associated with trigger '{trigger.name}' - adding it"
        )
        await sync_to_async(trigger.events.add)(event)

    return user, event


async def simulate_form_submission():
    """Simulate a form submission that would trigger the workflow."""
    user, event = await setup_test()

    if not event:
        logger.error("Setup failed - missing event or trigger")
        return 1

    # Create a BMI data object - using numbers that will result in a high BMI
    height = 180  # cm
    weight = 150  # kg
    bmi_data = BMIData(height, weight, user.id)

    logger.info(f"Simulating form submission for {user.username}")
    logger.info(f"Height: {height}cm, Weight: {weight}kg, BMI: {bmi_data.bmi}")

    # Fire the event (as if a form was submitted)
    # We're passing the BMI data as context for the workflow
    await sync_to_async(event.fire_single)(
        user.id,
        bmi=bmi_data.bmi,
        height=bmi_data.height_cm,
        weight=bmi_data.weight_kg,
        task_id=1,  # This is needed by the TaskCompletedEvent
    )

    logger.info("Event fired successfully")
    logger.info("Check your Temporal worker logs for workflow execution")

    return 0


async def main():
    """Main entry point for the script."""
    try:
        logger.info("Starting BMI form submission test")
        return await simulate_form_submission()
    except Exception as e:
        logger.exception(f"Error during test: {str(e)}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
