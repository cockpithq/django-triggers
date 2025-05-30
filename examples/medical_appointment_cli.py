#!/usr/bin/env python
"""
CLI script for the medical appointment scenario.

This script provides commands for setting up and testing the medical form workflow:
1. Setup: Creates a test user and trigger configuration
2. Submit: Submits a medical form to test the trigger workflow

To run this script:
1. Make sure you have run migrations
2. Run the Temporal worker: `python examples/run_temporal_worker.py`
3. Setup the test data: `python examples/medical_appointment_cli.py setup`
4. Submit a test form: `python examples/medical_appointment_cli.py submit`
"""

import argparse
import asyncio
import logging
import os
import sys

from asgiref.sync import sync_to_async
import django


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

# Now we can import Django models
from django.contrib.auth.models import User

from examples.models import (
    HighBMICondition,
    MedicalForm,
    MedicalFormSubmittedEvent,
    ScheduleDoctorAppointmentAction,
)
from triggers.models import Trigger


# --- Helper functions ---------------------------------------------------------


def create_example_user(
    username="patient", email="patient@example.com", password="password"
):
    """Create an example user for testing."""
    try:
        user = User.objects.get(username=username)
        logger.info(f"Using existing user: {user.username}")
    except User.DoesNotExist:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name="Test",
            last_name="Patient",
        )
        logger.info(f"Created new user: {user.username}")
    return user


def create_sample_trigger():
    """Create a sample trigger configuration."""
    # Check if trigger already exists
    trigger_name = "High BMI Doctor Referral"
    try:
        trigger = Trigger.objects.get(name=trigger_name)
        logger.info(f"Using existing trigger: {trigger.name}")
        return trigger
    except Trigger.DoesNotExist:
        pass

    # Create trigger first
    trigger = Trigger.objects.create(
        name=trigger_name,
        is_enabled=True,
    )
    logger.info(f"Created new trigger: {trigger.name}")

    # Create trigger components with trigger reference
    event = MedicalFormSubmittedEvent.objects.create(trigger=trigger)
    logger.info("Created medical form submitted event")

    condition = HighBMICondition.objects.create(
        trigger=trigger,
        threshold=45.0,
    )
    logger.info("Created high BMI condition with threshold 45.0")

    action = ScheduleDoctorAppointmentAction.objects.create(
        trigger=trigger,
        doctor_name="Dr. Jennifer Smith",
        days_ahead=5,
        appointment_reason_template="Follow-up for high BMI ({{ bmi }})",
    )
    logger.info("Created appointment scheduling action")

    # Add event to trigger
    trigger.events.add(event)

    return trigger


def submit_sample_form(
    user, height_cm=180, weight_kg=150, has_diabetes=False, has_hypertension=False
):
    """Submit a sample medical form to trigger the workflow."""
    form = MedicalForm.objects.create(
        user=user,
        height_cm=height_cm,
        weight_kg=weight_kg,
        has_diabetes=has_diabetes,
        has_hypertension=has_hypertension,
        current_medications="None",
    )

    bmi = form.bmi
    logger.info(f"Submitted form for {user.username} with BMI: {bmi}")
    logger.info(f"BMI exceeds 45: {bmi > 45}")
    return form


async def main():
    """Main function that sets up and runs the scenario."""
    parser = argparse.ArgumentParser(description="Medical Appointment Scenario")
    parser.add_argument("action", choices=["setup", "submit"], help="Action to perform")
    parser.add_argument("--height", type=int, default=180, help="Height in cm")
    parser.add_argument("--weight", type=int, default=150, help="Weight in kg")
    parser.add_argument("--diabetes", action="store_true", help="Has diabetes")
    parser.add_argument("--hypertension", action="store_true", help="Has hypertension")

    args = parser.parse_args()

    # Use sync_to_async for Django ORM operations
    create_user = sync_to_async(create_example_user)
    create_trigger = sync_to_async(create_sample_trigger)
    submit_form = sync_to_async(submit_sample_form)

    user = await create_user()

    if args.action == "setup":
        trigger = await create_trigger()
        logger.info("Setup complete. To test the scenario, run:")
        logger.info("python examples/medical_appointment_cli.py submit")

    elif args.action == "submit":
        await create_trigger()  # Ensure trigger exists

        # Adjust weight to ensure a high BMI if needed
        if args.height == 180 and args.weight == 150:
            logger.info("Using default values: height=180cm, weight=150kg (BMI=46.3)")

        form = await submit_form(
            user,
            height_cm=args.height,
            weight_kg=args.weight,
            has_diabetes=args.diabetes,
            has_hypertension=args.hypertension,
        )

        # Calculate BMI for display
        bmi = round((args.weight / ((args.height / 100) ** 2)), 1)
        logger.info(f"Form submitted with BMI: {bmi}")
        logger.info(
            "Check your terminal running the Temporal worker for workflow execution."
        )
        logger.info("If BMI > 45, an appointment should be scheduled.")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
