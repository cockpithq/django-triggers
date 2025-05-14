"""Medical form models."""

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import datetime
from django.utils import timezone
from django.template import Template, Context
from django.dispatch import receiver, Signal
import logging

from triggers.models import Event, Condition, Action


class MedicalForm(models.Model):
    """Medical form with patient health information."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="medical_forms",
        verbose_name=_("patient"),
    )
    height_cm = models.PositiveIntegerField(_("height (cm)"))
    weight_kg = models.PositiveIntegerField(_("weight (kg)"))
    has_diabetes = models.BooleanField(_("has diabetes"), default=False)
    has_hypertension = models.BooleanField(_("has hypertension"), default=False)
    current_medications = models.TextField(_("current medications"), blank=True)
    submission_date = models.DateTimeField(_("submission date"), auto_now_add=True)

    submitted = Signal()

    class Meta:
        verbose_name = _("medical form")
        verbose_name_plural = _("medical forms")

    def __str__(self):
        return f"Medical Form for {self.user.username} ({self.submission_date.date()})"

    @property
    def bmi(self):
        """Calculate the BMI (Body Mass Index)."""
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m * height_m), 1)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        result = super().save(*args, **kwargs)
        if is_new:
            # Send the submitted signal when the form is first created
            self.submitted.send(sender=self.__class__, form=self)
        return result


class DoctorAppointment(models.Model):
    """Doctor appointment scheduled for a patient."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name=_("patient"),
    )
    appointment_date = models.DateTimeField(_("appointment date"))
    doctor_name = models.CharField(_("doctor name"), max_length=100)
    reason = models.TextField(_("reason"))
    is_confirmed = models.BooleanField(_("confirmed"), default=False)

    class Meta:
        verbose_name = _("doctor appointment")
        verbose_name_plural = _("doctor appointments")

    def __str__(self):
        return f"Appointment with {self.doctor_name} on {self.appointment_date}"


class MedicalFormSubmittedEvent(Event):
    """Event that triggers when a medical form is submitted."""

    class Meta:
        verbose_name = _("medical form submitted")

    def should_be_fired(self, **kwargs) -> bool:
        return True

    def get_user_context(self, user, context):
        user_context = super().get_user_context(user, context)
        # Add BMI to context if available
        if "bmi" in context:
            user_context["bmi"] = context["bmi"]
        if "height" in context:
            user_context["height"] = context["height"]
        if "weight" in context:
            user_context["weight"] = context["weight"]
        return user_context


@receiver(MedicalForm.submitted)
def on_medical_form_submitted(sender, form, **kwargs):
    """Handle the medical form submission and fire events."""
    for event in MedicalFormSubmittedEvent.objects.all():
        # Pass the BMI and other form data as context
        event.fire_single(
            form.user.id,
            bmi=form.bmi,
            height=form.height_cm,
            weight=form.weight_kg,
        )


class HighBMICondition(Condition):
    """Condition that checks if a patient's BMI exceeds a threshold."""

    threshold = models.DecimalField(
        _("BMI threshold"),
        max_digits=4,
        decimal_places=1,
        default=45.0,
        help_text=_("Trigger action if BMI exceeds this value"),
    )

    class Meta:
        verbose_name = _("high BMI condition")

    def is_satisfied(self, user) -> bool:
        # In a real app, we'd check the user's most recent form
        # For this example, we'll use the context directly in perform_action
        # This method will always return True, the actual check happens when
        # we access the BMI value from context
        logger = logging.getLogger(__name__)
        logger.info(
            f"🔍 Checking if user {user.username} has BMI above threshold of {self.threshold}"
        )

        # Try to get the most recent form to check BMI
        try:
            latest_form = MedicalForm.objects.filter(user=user).latest(
                "submission_date"
            )
            bmi = latest_form.bmi
            logger.info(f"📊 Found BMI value from latest form: {bmi}")

            result = bmi > float(self.threshold)
            if result:
                logger.info(
                    f"⚠️ High BMI detected: {bmi} > {self.threshold} - condition SATISFIED"
                )
            else:
                logger.info(
                    f"✓ BMI {bmi} is below threshold {self.threshold} - condition NOT SATISFIED"
                )

            return result
        except MedicalForm.DoesNotExist:
            # If we can't find a form, we'll defer to the context check in the action
            logger.info("ℹ️ No medical form found - deferring to action context check")
            return True

    def __str__(self):
        return f"BMI > {self.threshold}"


class HasDiabetesCondition(Condition):
    """Condition that checks if a patient has diabetes."""

    class Meta:
        verbose_name = _("has diabetes condition")

    def is_satisfied(self, user) -> bool:
        # Check the user's most recent medical form
        try:
            latest_form = MedicalForm.objects.filter(user=user).latest(
                "submission_date"
            )
            return latest_form.has_diabetes
        except MedicalForm.DoesNotExist:
            return False


class ScheduleDoctorAppointmentAction(Action):
    """Action that schedules a doctor appointment for high BMI patients."""

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

    class Meta:
        verbose_name = _("schedule doctor appointment")

    def perform(self, user, context):
        # Check the BMI in the context
        bmi = context.get("bmi", 0)
        height = context.get("height", 0)
        weight = context.get("weight", 0)

        logger = logging.getLogger(__name__)
        logger.info(
            f"🩺 Evaluating appointment need for patient {user.username} (BMI: {bmi})"
        )

        # Only proceed if BMI exceeds our threshold (as a backup check)
        if bmi <= 45:
            logger.info(f"✓ No appointment needed - BMI {bmi} is below threshold of 45")
            return

        logger.info(
            f"⚠️ High BMI detected: {bmi} (height: {height}cm, weight: {weight}kg)"
        )

        # Calculate appointment date
        appointment_date = timezone.now() + datetime.timedelta(days=self.days_ahead)

        # Create personalized reason using template
        template = Template(self.appointment_reason_template)
        reason = template.render(Context(context))

        logger.info(
            f"📅 Scheduling appointment with {self.doctor_name} on {appointment_date.strftime('%Y-%m-%d')}"
        )
        logger.info(f"📝 Reason: {reason}")

        # Create the appointment
        appointment = DoctorAppointment.objects.create(
            user=user,
            appointment_date=appointment_date,
            doctor_name=self.doctor_name,
            reason=reason,
        )

        logger.info(f"✅ Appointment #{appointment.pk} created successfully")

        # Notify the user (in a real app, this would send an email)
        user.email_user(
            subject="Doctor Appointment Scheduled",
            message=(
                f"Dear {user.first_name or user.username},\n\n"
                f"A doctor appointment has been scheduled for you on "
                f"{appointment_date.strftime('%Y-%m-%d at %H:%M')}.\n\n"
                f"Doctor: {self.doctor_name}\n"
                f"Reason: {reason}\n\n"
                f"Please contact us if you need to reschedule.\n\n"
                f"Regards,\nMedical Team"
            ),
        )

        logger.info(f"📧 Email notification sent to {user.email}")

        return appointment
