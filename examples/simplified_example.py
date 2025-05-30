#!/usr/bin/env python
"""
Simplified example for demonstrating Temporal integration with django-triggers.

This script creates simple workflow for the BMI-based appointment scheduling scenario.

Usage:
    python simplified_example.py
"""

import asyncio
import logging
import os
import sys


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

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from triggers.models import Action, Condition, Event, Trigger


class BMICheckEvent(Event):
    """Event that fires when a BMI check is performed."""

    class Meta(Event.Meta):
        verbose_name = "BMI check"

    def should_be_fired(self, **kwargs) -> bool:
        return True

    def get_user_context(self, user, context) -> dict:
        context = super().get_user_context(user, context)
        context.update(
            {
                "bmi": context.get("bmi", 0),
                "height": context.get("height", 0),
                "weight": context.get("weight", 0),
            }
        )
        return context


class HighBMICondition(Condition):
    """Condition that checks if BMI exceeds a threshold."""

    class Meta(Condition.Meta):
        verbose_name = "high BMI condition"

    def is_satisfied(self, user) -> bool:
        # In a real app, would check BMI from database
        # For demo purposes, just return True
        return True


class ScheduleAppointmentAction(Action):
    """Action that schedules a doctor appointment."""

    class Meta(Action.Meta):
        verbose_name = "schedule appointment action"

    def perform(self, user, context):
        bmi = context.get("bmi", 0)
        logger.info(f"Scheduling appointment for {user.username} with BMI: {bmi}")

        # In a real app, would create appointment
        logger.info(f"Appointment scheduled with Dr. Smith for {user.username}")

        # Send email notification
        user.email_user(
            subject="Doctor Appointment Scheduled",
            message=f"Dear {user.username},\n\nA doctor appointment has been scheduled for you due to your BMI of {bmi}.\n\nRegards,\nMedical Team",
        )


async def setup_trigger():
    """Set up the trigger, condition, and action."""
    # Get or create a test user
    try:
        user = await sync_to_async(User.objects.get)(username="testuser")
        logger.info(f"Using existing user: {user.username}")
    except User.DoesNotExist:
        user = await sync_to_async(User.objects.create_user)(
            username="testuser", email="test@example.com", password="password"
        )
        logger.info(f"Created new user: {user.username}")

    # Create or get BMI check event
    try:
        event = await sync_to_async(BMICheckEvent.objects.get)(name="BMI Check")
        logger.info(f"Using existing event: {event.name}")
    except BMICheckEvent.DoesNotExist:
        event = await sync_to_async(BMICheckEvent.objects.create)(name="BMI Check")
        logger.info(f"Created new event: {event.name}")

    # Create or get high BMI condition
    try:
        condition = await sync_to_async(HighBMICondition.objects.get)(name="BMI > 45")
        logger.info(f"Using existing condition: {condition.name}")
    except HighBMICondition.DoesNotExist:
        condition = await sync_to_async(HighBMICondition.objects.create)(
            name="BMI > 45"
        )
        logger.info(f"Created new condition: {condition.name}")

    # Create or get appointment action
    try:
        action = await sync_to_async(ScheduleAppointmentAction.objects.get)(
            name="Schedule Dr. Appointment"
        )
        logger.info(f"Using existing action: {action.name}")
    except ScheduleAppointmentAction.DoesNotExist:
        action = await sync_to_async(ScheduleAppointmentAction.objects.create)(
            name="Schedule Dr. Appointment"
        )
        logger.info(f"Created new action: {action.name}")

    # Create or get the trigger
    try:
        trigger = await sync_to_async(Trigger.objects.get)(name="High BMI Appointment")
        logger.info(f"Using existing trigger: {trigger.name}")
    except Trigger.DoesNotExist:
        trigger = await sync_to_async(Trigger.objects.create)(
            name="High BMI Appointment", is_enabled=True
        )
        # Link components to the trigger
        await sync_to_async(trigger.events.add)(event)
        await sync_to_async(trigger.conditions.add)(condition)
        await sync_to_async(trigger.actions.add)(action)
        logger.info(f"Created new trigger: {trigger.name}")

    return user, event


async def fire_bmi_event():
    """Fire a BMI check event to trigger the workflow."""
    user, event = await setup_trigger()

    # Calculate a BMI value (example: 180cm, 150kg)
    height = 180  # cm
    weight = 150  # kg
    bmi = round(weight / ((height / 100) ** 2), 1)

    logger.info(f"Firing BMI check event for {user.username} with BMI: {bmi}")

    # Fire the event
    await sync_to_async(event.fire_single)(
        user.id, bmi=bmi, height=height, weight=weight
    )

    logger.info("Event fired. Check your Temporal worker logs.")
    logger.info("You should see the workflow executing and scheduling an appointment.")


async def main():
    """Main entry point for the script."""
    logger.info("Setting up trigger and firing event...")
    await fire_bmi_event()
    logger.info("Done.")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Script interrupted by user.")
        sys.exit(1)
