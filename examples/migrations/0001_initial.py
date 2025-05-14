from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("triggers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MedicalForm",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("height_cm", models.PositiveIntegerField(verbose_name="height (cm)")),
                ("weight_kg", models.PositiveIntegerField(verbose_name="weight (kg)")),
                (
                    "has_diabetes",
                    models.BooleanField(default=False, verbose_name="has diabetes"),
                ),
                (
                    "has_hypertension",
                    models.BooleanField(default=False, verbose_name="has hypertension"),
                ),
                (
                    "current_medications",
                    models.TextField(blank=True, verbose_name="current medications"),
                ),
                (
                    "submission_date",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="submission date"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="medical_forms",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="patient",
                    ),
                ),
            ],
            options={
                "verbose_name": "medical form",
                "verbose_name_plural": "medical forms",
            },
        ),
        migrations.CreateModel(
            name="DoctorAppointment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "appointment_date",
                    models.DateTimeField(verbose_name="appointment date"),
                ),
                (
                    "doctor_name",
                    models.CharField(max_length=100, verbose_name="doctor name"),
                ),
                ("reason", models.TextField(verbose_name="reason")),
                (
                    "is_confirmed",
                    models.BooleanField(default=False, verbose_name="confirmed"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="appointments",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="patient",
                    ),
                ),
            ],
            options={
                "verbose_name": "doctor appointment",
                "verbose_name_plural": "doctor appointments",
            },
        ),
        migrations.CreateModel(
            name="MedicalFormSubmittedEvent",
            fields=[
                (
                    "event_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="triggers.event",
                    ),
                ),
            ],
            options={
                "verbose_name": "medical form submitted",
            },
            bases=("triggers.event",),
        ),
        migrations.CreateModel(
            name="HighBMICondition",
            fields=[
                (
                    "condition_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="triggers.condition",
                    ),
                ),
                (
                    "threshold",
                    models.DecimalField(
                        decimal_places=1,
                        default=45.0,
                        help_text="Trigger action if BMI exceeds this value",
                        max_digits=4,
                        verbose_name="BMI threshold",
                    ),
                ),
            ],
            options={
                "verbose_name": "high BMI condition",
            },
            bases=("triggers.condition",),
        ),
        migrations.CreateModel(
            name="HasDiabetesCondition",
            fields=[
                (
                    "condition_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="triggers.condition",
                    ),
                ),
            ],
            options={
                "verbose_name": "has diabetes condition",
            },
            bases=("triggers.condition",),
        ),
        migrations.CreateModel(
            name="ScheduleDoctorAppointmentAction",
            fields=[
                (
                    "action_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="triggers.action",
                    ),
                ),
                (
                    "days_ahead",
                    models.PositiveIntegerField(
                        default=7,
                        help_text="Schedule appointment this many days in the future",
                        verbose_name="days ahead",
                    ),
                ),
                (
                    "doctor_name",
                    models.CharField(max_length=100, verbose_name="doctor name"),
                ),
                (
                    "appointment_reason_template",
                    models.TextField(
                        default="Follow-up for BMI of {{ bmi }}",
                        help_text="You can use Django template language",
                        verbose_name="appointment reason template",
                    ),
                ),
            ],
            options={
                "verbose_name": "schedule doctor appointment",
            },
            bases=("triggers.action",),
        ),
    ]
