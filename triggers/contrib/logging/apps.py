from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LoggingConfig(AppConfig):
    name = "triggers.contrib.logging"
    verbose_name = _("Trigger logging")
