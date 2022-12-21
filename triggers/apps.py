from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DefaultConfig(AppConfig):
    name = 'triggers'
    verbose_name = _('Triggers')

    def ready(self):
        # Connect `triggers.tasks.on_event_fired` to `Event.fired` signal
        from triggers import tasks  # noqa: F401
