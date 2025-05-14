#!/usr/bin/env python
"""
Create test data for the Temporal integration.

This script creates a test trigger and event in the database if none exist.
"""

import os
import django

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
django.setup()

from django.contrib.auth.models import User
from triggers.models import Trigger, Event
from tests.app.models import ClockEvent
from model_bakery import baker

# Create a user if none exists
if User.objects.count() == 0:
    user = User.objects.create_user(
        username="test_user", email="test@example.com", password="password"
    )
    print(f"Created User: {user.username}")

# Create a trigger if none exists
if not Trigger.objects.exists():
    trigger = baker.make(Trigger, name="Test Trigger", is_enabled=True)
    print(f"Created Trigger: {trigger}")

    # Create a clock event for the trigger
    event = baker.make(ClockEvent, trigger=trigger)
    print(f"Created Event: {event}")

# Print summary
print(f"Users count: {User.objects.count()}")
print(f"Triggers count: {Trigger.objects.count()}")
print(f"Events count: {Event.objects.count()}")
