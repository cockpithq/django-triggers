from typing import Any

from django.conf import settings


def log_trigger_event(*args: Any, **kwargs: Any):
    if "triggers.contrib.logging" in settings.INSTALLED_APPS:
        from triggers.contrib.logging.models import log_trigger_event as real
        return real(*args, **kwargs)
    return None
