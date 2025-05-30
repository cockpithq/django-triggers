#!/usr/bin/env python
"""
Simple script to check what's in the database.
"""

import os

import django


# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
django.setup()

from examples.models import (
    HighBMICondition,
    MedicalFormSubmittedEvent,
    ScheduleDoctorAppointmentAction,
)
from triggers.models import Action, Condition, Event, Trigger


print("=== Triggers ===")
for trigger in Trigger.objects.all():
    print(f"Trigger: {trigger.name} (ID: {trigger.pk}, Enabled: {trigger.is_enabled})")
    print(f"Events: {list(trigger.events.all())}")
    print(f"Conditions: {list(trigger.conditions.all())}")
    print(f"Actions: {list(trigger.actions.all())}")
    print()

print("\n=== Events ===")
for event in Event.objects.all():
    print(f"Event: {event} (ID: {event.pk}, Type: {event.__class__.__name__})")
    print(f"Trigger: {event.trigger}")
    print()

print("\n=== MedicalFormSubmittedEvent ===")
print(list(MedicalFormSubmittedEvent.objects.all()))

print("\n=== Conditions ===")
for condition in Condition.objects.all():
    print(
        f"Condition: {condition} (ID: {condition.pk}, Type: {condition.__class__.__name__})"
    )
    print(f"Trigger: {condition.trigger}")
    print()

print("\n=== HighBMICondition ===")
print(list(HighBMICondition.objects.all()))

print("\n=== Actions ===")
for action in Action.objects.all():
    print(f"Action: {action} (ID: {action.pk}, Type: {action.__class__.__name__})")
    print(f"Trigger: {action.trigger}")
    print()

print("\n=== ScheduleDoctorAppointmentAction ===")
print(list(ScheduleDoctorAppointmentAction.objects.all()))
