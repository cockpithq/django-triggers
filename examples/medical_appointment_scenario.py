#!/usr/bin/env python
"""
Medical Appointment Scheduling Scenario for django-triggers with Temporal.

This example demonstrates:
1. A medical form submission trigger
2. A BMI check condition (BMI > 45)
3. A doctor appointment scheduling action

To run this example:
1. Make sure you have a Temporal server running
2. Create the models with Django migrations
3. Set up triggers in the Django admin
4. Run the Temporal worker: `python examples/run_temporal_worker.py`
5. Submit a form to test the trigger: `python examples/medical_appointment_scenario.py submit`
"""

import os
import sys
import asyncio
import logging
import django
import argparse
from datetime import datetime, timedelta
from django.db import models, transaction
from django.dispatch import receiver, Signal
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from asgiref.sync import sync_to_async

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Set up Django environment but only when this file is executed directly
# When imported as a module, Django will already be set up
if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")
    django.setup()

# Now import django-triggers components
from triggers.models import Action, Condition, Event, Trigger


# --- Models -------------------------------------------------------------------


class MedicalForm(models.Model):
    """Medical intake form with patient information."""

    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        verbose_name=_("patient"),
        related_name="medical_forms",
    )
    height_cm = models.PositiveIntegerField(_("height (cm)"))
    weight_kg = models.PositiveIntegerField(_("weight (kg)"))
    has_diabetes = models.BooleanField(_("has diabetes"), default=False)
    has_hypertension = models.BooleanField(_("has hypertension"), default=False)
    current_medications = models.TextField(_("current medications"), blank=True)
    submission_date = models.DateTimeField(_("submission date"), auto_now_add=True)

    # Signal emitted when form is submitted
    submitted = Signal()

    class Meta:
        verbose_name = _("medical form")
        verbose_name_plural = _("medical forms")

    def __str__(self):
        return f"Medical Form for {self.user.username} ({self.submission_date.strftime('%Y-%m-%d')})"

    @property
    def bmi(self):
        """Calculate Body Mass Index (BMI)."""
        if self.height_cm and self.weight_kg:
            height_m = self.height_cm / 100
            return round(self.weight_kg / (height_m * height_m), 1)
        return None

    def save(self, *args, **kwargs):
        is_new = not self.pk
        result = super().save(*args, **kwargs)
        if is_new:
            self.submitted.send(sender=self.__class__, form=self)
        return result


class DoctorAppointment(models.Model):
    """Doctor appointment record."""

    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        verbose_name=_("patient"),
        related_name="appointments",
    )
    appointment_date = models.DateTimeField(_("appointment date"))
    doctor_name = models.CharField(_("doctor name"), max_length=100)
    reason = models.TextField(_("reason"))
    is_confirmed = models.BooleanField(_("confirmed"), default=False)

    class Meta:
        verbose_name = _("doctor appointment")
        verbose_name_plural = _("doctor appointments")

    def __str__(self):
        return f"Appointment with {self.doctor_name} for {self.user.username} on {self.appointment_date.strftime('%Y-%m-%d %H:%M')}"


# --- Events -------------------------------------------------------------------


class MedicalFormSubmittedEvent(Event):
    """Event triggered when a medical form is submitted."""

    class Meta(Event.Meta):
        verbose_name = _("medical form submitted")

    def should_be_fired(self, **kwargs) -> bool:
        # Always fire when a form is submitted
        return True

    def get_user_context(self, user, context) -> dict:
        user_context = super().get_user_context(user, context)
        form = MedicalForm.objects.get(id=context["form_id"])
        user_context.update(
            {
                "form": form,
                "bmi": form.bmi,
                "submission_date": form.submission_date,
            }
        )
        return user_context


@receiver(MedicalForm.submitted)
def on_medical_form_submitted(sender, form: MedicalForm, **kwargs):
    """Listen for medical form submission and fire the event."""
    event: MedicalFormSubmittedEvent
    for event in MedicalFormSubmittedEvent.objects.all():
        transaction.on_commit(lambda: event.fire_single(form.user_id, form_id=form.id))


# --- Conditions ---------------------------------------------------------------


class HighBMICondition(Condition):
    """Condition that checks if patient's BMI exceeds a threshold."""

    threshold = models.DecimalField(
        _("BMI threshold"),
        max_digits=4,
        decimal_places=1,
        default=45.0,
        help_text=_("Trigger action if BMI exceeds this value"),
    )

    class Meta(Condition.Meta):
        verbose_name = _("high BMI condition")

    def is_satisfied(self, user: User) -> bool:
        # Check the most recent form
        try:
            latest_form = MedicalForm.objects.filter(user=user).latest(
                "submission_date"
            )
            return latest_form.bmi > float(self.threshold)
        except MedicalForm.DoesNotExist:
            return False


class HasDiabetesCondition(Condition):
    """Condition that checks if patient has diabetes."""

    class Meta(Condition.Meta):
        verbose_name = _("has diabetes condition")

    def is_satisfied(self, user: User) -> bool:
        try:
            latest_form = MedicalForm.objects.filter(user=user).latest(
                "submission_date"
            )
            return latest_form.has_diabetes
        except MedicalForm.DoesNotExist:
            return False


# --- Actions ------------------------------------------------------------------


class ScheduleDoctorAppointmentAction(Action):
    """Action that schedules a doctor appointment for the patient."""

    days_ahead = models.PositiveIntegerField(
        _("days ahead"),
        default=7,
        help_text=_("Schedule appointment this many days in the future"),
    )
    doctor_name = models.CharField(_("doctor name"), max_length=100)
    appointment_reason_template = models.TextField(
        _("appointment reason template"),
        default="Follow-up for BMI of {{ bmi }}",
        help_text=_("You can use Django template language"),
    )

    class Meta(Action.Meta):
        verbose_name = _("schedule doctor appointment")

    def perform(self, user: User, context: dict):
        from django.template import Template, Context

        # Calculate appointment date
        appointment_date = datetime.now() + timedelta(days=self.days_ahead)

        # Use template to generate reason
        template = Template(self.appointment_reason_template)
        reason = template.render(Context(context))

        # Create appointment
        appointment = DoctorAppointment.objects.create(
            user=user,
            appointment_date=appointment_date,
            doctor_name=self.doctor_name,
            reason=reason,
        )

        logger.info(f"Scheduled appointment: {appointment}")

        # Send notification email
        user.email_user(
            subject=f"Doctor Appointment Scheduled: {appointment_date.strftime('%Y-%m-%d')}",
            message=f"""
Dear {user.first_name or user.username},

A doctor appointment has been scheduled for you:

Doctor: {self.doctor_name}
Date: {appointment_date.strftime('%A, %B %d, %Y')}
Time: {appointment_date.strftime('%I:%M %p')}
Reason: {reason}

Please confirm this appointment by logging into your patient portal.

Thank you,
Medical Center Staff
""",
        )


# --- Helper functions ---------------------------------------------------------


def create_example_user(
    username="patient", email="patient@example.com", password="password"
):
    """Create an example user for testing."""
    User = django.contrib.auth.get_user_model()
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

    # Create trigger components
    event = MedicalFormSubmittedEvent.objects.create(name="Medical Form Submission")

    condition = HighBMICondition.objects.create(name="BMI > 45", threshold=45.0)

    action = ScheduleDoctorAppointmentAction.objects.create(
        name="Schedule Appointment with Dr. Smith",
        doctor_name="Dr. Jennifer Smith",
        days_ahead=5,
        appointment_reason_template="Follow-up for high BMI ({{ bmi }})",
    )

    # Create trigger
    trigger = Trigger.objects.create(
        name=trigger_name,
        is_enabled=True,
    )

    # Add components to trigger
    trigger.events.add(event)
    trigger.conditions.add(condition)
    trigger.actions.add(action)

    logger.info(f"Created new trigger: {trigger.name}")
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
        logger.info("python examples/medical_appointment_scenario.py submit")

    elif args.action == "submit":
        await create_trigger()  # Ensure trigger exists
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
