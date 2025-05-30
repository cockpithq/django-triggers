from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DefaultConfig(AppConfig):
    name = "triggers"
    verbose_name = _("Triggers")

    def ready(self):
        # Connect `triggers.tasks.on_event_fired` to `Event.fired` signal if
        # Celery is available. This allows using alternative backends like
        # Temporal or handling triggers manually without Celery installed.
        try:
            from triggers import tasks  # noqa: F401
        except Exception:  # pragma: no cover - optional dependency
            pass
