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
    level=logging.DEBUG,  # Changed to DEBUG for more verbose output
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Enable debug logging for the triggers module
logging.getLogger("triggers").setLevel(logging.DEBUG)
logging.getLogger("triggers.temporal").setLevel(logging.DEBUG)

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
import django

django.setup()

from django.contrib.auth.models import User
from asgiref.sync import sync_to_async
from triggers.models import Trigger
from examples.models import MedicalForm, MedicalFormSubmittedEvent


async def setup_test():
    """Set up the test data (user and trigger)."""
    # Get or create a test user
    try:
        user = await sync_to_async(User.objects.get)(username="patient")
        logger.info(f"Using existing user: {user.username}")
    except User.DoesNotExist:
        user = await sync_to_async(User.objects.create_user)(
            username="patient",
            email="patient@example.com",
            password="password",
            first_name="Test",
            last_name="Patient",
        )
        logger.info(f"Created new user: {user.username}")

    # Get the event in the database
    try:
        event = await sync_to_async(MedicalFormSubmittedEvent.objects.first)()
        if not event:
            logger.error("No MedicalFormSubmittedEvent found in the database")
            return None, None
        logger.info(f"Using event: {event}")
    except Exception as e:
        logger.error(f"Error getting event: {e}")
        return None, None

    # Debug: Print event details
    logger.debug(f"Event ID: {event.pk}, Event type: {event.__class__.__name__}")

    # Check if event has a trigger
    trigger_id = await sync_to_async(getattr)(event, "trigger_id", None)
    logger.debug(f"Event's trigger_id: {trigger_id}")

    # Get the trigger from the database
    try:
        trigger = await sync_to_async(Trigger.objects.get)(
            name="High BMI Doctor Referral"
        )
        logger.info(f"Using trigger: {trigger.name}")
    except Trigger.DoesNotExist:
        logger.error(
            "High BMI Doctor Referral trigger not found. Run setup_db.py first."
        )
        return user, None

    # Debug: Print trigger details
    logger.debug(f"Trigger ID: {trigger.pk}, Enabled: {trigger.is_enabled}")

    # Debug: List conditions and actions
    conditions = await sync_to_async(list)(trigger.conditions.all())
    actions = await sync_to_async(list)(trigger.actions.all())
    logger.debug(f"Trigger has {len(conditions)} conditions and {len(actions)} actions")
    for i, condition in enumerate(conditions):
        logger.debug(f"Condition {i+1}: {condition}")
    for i, action in enumerate(actions):
        logger.debug(f"Action {i+1}: {action}")

    # Check if the trigger is enabled
    if not trigger.is_enabled:
        logger.warning(f"Trigger '{trigger.name}' is not enabled - enabling it")
        trigger.is_enabled = True
        await sync_to_async(trigger.save)()

    return user, event


async def simulate_form_submission():
    """Simulate a form submission that would trigger the workflow."""
    user, event = await setup_test()

    if not event:
        logger.error("Setup failed - missing event or trigger")
        return 1

    # Create medical form with high BMI
    height = 180  # cm
    weight = 150  # kg

    logger.info(f"Simulating medical form submission for {user.username}")
    logger.info(f"Height: {height}cm, Weight: {weight}kg")

    # Debug: Check triggers_settings
    from triggers import settings as triggers_settings

    logger.debug(f"TRIGGERS_USE_TEMPORAL: {triggers_settings.TRIGGERS_USE_TEMPORAL}")
    logger.debug(f"TEMPORAL_TASK_QUEUE: {triggers_settings.TEMPORAL_TASK_QUEUE}")

    # Debug: Directly examining Event signal and handler
    logger.debug(f"Signal defined on Event: {getattr(event.__class__, 'fired', None)}")

    from triggers.temporal.hooks import on_event_fired

    logger.debug(f"Event signal handler: {on_event_fired}")

    # Create the form - this should trigger the MedicalForm.submitted signal
    form = await sync_to_async(MedicalForm.objects.create)(
        user=user,
        height_cm=height,
        weight_kg=weight,
        has_diabetes=False,
        has_hypertension=False,
        current_medications="None",
    )

    # Calculate BMI for display
    bmi = await sync_to_async(getattr)(form, "bmi")
    logger.info(f"Form created with BMI: {bmi}")

    # Manually fire the event with explicit debug
    logger.info("Manually firing the event...")

    # Calculate expected workflow ID
    workflow_id = f"trigger-{event.trigger_id}-{user.id}-{event.pk}"
    logger.debug(f"Expected workflow ID: {workflow_id}")

    # First get the receiver functions for the Event.fired signal
    signal = event.__class__.fired
    logger.debug(f"Signal receivers: {list(signal.receivers)}")

    await sync_to_async(event.fire_single)(
        user.id,
        bmi=bmi,
        height=height,
        weight=weight,
    )

    logger.info("Form submitted and event fired successfully")
    logger.info("Check your Temporal worker logs for workflow execution")

    return 0


async def main():
    """Main entry point for the script."""
    try:
        logger.info("Starting medical form submission test")
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
