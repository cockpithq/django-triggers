#!/usr/bin/env python
"""
Script to set up the database for the medical form workflow example.
"""

import os
import django

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
django.setup()

from django.contrib.auth.models import User
from triggers.models import Trigger
from examples.models import (
    MedicalFormSubmittedEvent,
    HighBMICondition,
    ScheduleDoctorAppointmentAction,
)

# Create test user
user, created = User.objects.get_or_create(
    username="patient",
    defaults={
        "email": "patient@example.com",
        "first_name": "Test",
        "last_name": "Patient",
    },
)
if created:
    user.set_password("password")
    user.save()
    print(f"Created user: {user.username}")
else:
    print(f"Using existing user: {user.username}")

# Create trigger
trigger, created = Trigger.objects.get_or_create(
    name="High BMI Doctor Referral",
    defaults={"is_enabled": True},
)
print(f"{'Created' if created else 'Using existing'} trigger: {trigger.name}")

# Create event
event, created = MedicalFormSubmittedEvent.objects.get_or_create(
    trigger=trigger,
)
print(f"{'Created' if created else 'Using existing'} event: {event}")

# Create condition
condition, created = HighBMICondition.objects.get_or_create(
    trigger=trigger,
    defaults={"threshold": 45.0},
)
print(f"{'Created' if created else 'Using existing'} condition: {condition}")

# Create action
action, created = ScheduleDoctorAppointmentAction.objects.get_or_create(
    trigger=trigger,
    defaults={
        "doctor_name": "Dr. Jennifer Smith",
        "days_ahead": 5,
        "appointment_reason_template": "Follow-up for high BMI ({{ bmi }})",
    },
)
print(f"{'Created' if created else 'Using existing'} action: {action}")

# Make sure the event is associated with the trigger
if event not in trigger.events.all():
    trigger.events.add(event)
    print("Added event to trigger")
else:
    print("Event already associated with trigger")

print("\nSetup complete. You can now run the test with:")
print("python examples/test_form_submit.py")
