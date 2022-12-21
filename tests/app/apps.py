from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BillingConfig(AppConfig):
    name = 'tests.app'
    verbose_name = _('Test app')

    def ready(self):
        # Initialize Celery app
        from tests.app import celery  # noqa: F401
