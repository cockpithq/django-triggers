from functools import lru_cache
from typing import Any, Mapping, Optional

from django.conf import settings
from django.test.signals import setting_changed
from django.utils.module_loading import import_string


TRACE_ID_CONTEXT_KEY = "_triggers_trace_id"
OBSERVER_CLASS_SETTING = "TRIGGERS_OBSERVER"


class TriggerObserver:
    """Hook points for observing trigger pipeline execution."""

    def on_event_enqueued(
        self,
        *,
        run_id: str,
        event,
        user_pk: Any,
        context: Mapping[str, Any],
    ) -> None:
        return None

    def on_event_started(
        self,
        *,
        run_id: str,
        event,
        user_pk: Any,
        context: Mapping[str, Any],
    ) -> None:
        return None

    def on_user_resolved(
        self,
        *,
        run_id: str,
        event,
        user_pk: Any,
        is_found: bool,
    ) -> None:
        return None

    def on_condition_checked(
        self,
        *,
        run_id: str,
        trigger,
        user_pk: Any,
        condition,
        is_satisfied: bool,
    ) -> None:
        return None

    def on_action_performed(
        self,
        *,
        run_id: str,
        trigger,
        user_pk: Any,
        action,
    ) -> None:
        return None

    def on_action_failed(
        self,
        *,
        run_id: str,
        trigger,
        user_pk: Any,
        action,
        error: Exception,
    ) -> None:
        return None

    def on_run_completed(
        self,
        *,
        run_id: str,
        event,
        trigger,
        user_pk: Any,
        result: str,
    ) -> None:
        return None


class NoOpTriggerObserver(TriggerObserver):
    pass


@lru_cache(maxsize=1)
def get_trigger_observer() -> TriggerObserver:
    observer_class_path: Optional[str] = getattr(settings, OBSERVER_CLASS_SETTING, None)
    if not observer_class_path:
        return NoOpTriggerObserver()
    observer_class = import_string(observer_class_path)
    return observer_class()


def _clear_observer_cache(*_args, **kwargs):
    if kwargs.get("setting") == OBSERVER_CLASS_SETTING:
        get_trigger_observer.cache_clear()


setting_changed.connect(_clear_observer_cache)
