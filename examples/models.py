"""
Models for the examples package.

This file imports and re-exports the models defined in medical_appointment_scenario.py
so they can be properly registered with Django.
"""

# Import models so they are registered with Django
from examples.medical_appointment_scenario import (
    # Base models
    MedicalForm,
    DoctorAppointment,
    # Event models
    MedicalFormSubmittedEvent,
    # Condition models
    HighBMICondition,
    HasDiabetesCondition,
    # Action models
    ScheduleDoctorAppointmentAction,
)

# Export the models for Django to find them
__all__ = [
    "MedicalForm",
    "DoctorAppointment",
    "MedicalFormSubmittedEvent",
    "HighBMICondition",
    "HasDiabetesCondition",
    "ScheduleDoctorAppointmentAction",
]
