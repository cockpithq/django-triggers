from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BillingConfig(AppConfig):
    name = 'tests.app'
    verbose_name = _('Test app')

    def ready(self):
        from .celery import app
        app.autodiscover_tasks(force=True)
