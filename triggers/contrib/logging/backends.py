from typing import Any, Mapping

from django.contrib.auth import get_user_model
from django.utils import timezone

from triggers.contrib.logging.models import TriggerExecutionLog
from triggers.observers import TriggerObserver

User = get_user_model()


class DBExecutionLogBackend(TriggerObserver):
    STEP_EVENT_STARTED = 1
    STEP_USER_RESOLVED = 2
    STEP_CONDITION_CHECKED = 3
    STEP_ACTION_PERFORMED = 4

    def _append_step(self, *, run_id: str, step):
        execution_log = TriggerExecutionLog.objects.filter(run_id=run_id).first()
        if not execution_log:
            return
        steps = list(execution_log.steps)
        steps.append(step)
        TriggerExecutionLog.objects.filter(pk=execution_log.pk).update(steps=steps)

    def _get_or_create_log(
        self,
        *,
        run_id: str,
        event,
        user_pk: Any,
    ) -> TriggerExecutionLog:
        event_content_type_id = getattr(event, "polymorphic_ctype_id", None)
        user_id = user_pk if User.objects.filter(pk=user_pk).exists() else None
        execution_log, _created = TriggerExecutionLog.objects.get_or_create(
            run_id=run_id,
            defaults={
                "user_id": user_id,
                "trigger": event.trigger,
                "event_content_type_id": event_content_type_id,
                "event_object_id": event.pk,
            },
        )
        return execution_log

    def on_event_enqueued(
        self,
        *,
        run_id: str,
        event,
        user_pk: Any,
        context: Mapping[str, Any],
    ) -> None:
        try:
            self._get_or_create_log(run_id=run_id, event=event, user_pk=user_pk)
        except Exception:
            return None
        return None

    def on_event_started(
        self,
        *,
        run_id: str,
        event,
        user_pk: Any,
        context: Mapping[str, Any],
    ) -> None:
        try:
            self._get_or_create_log(run_id=run_id, event=event, user_pk=user_pk)
            TriggerExecutionLog.objects.filter(run_id=run_id).update(
                status=TriggerExecutionLog.STATUS_STARTED,
                started_at=timezone.now(),
            )
            self._append_step(run_id=run_id, step=[self.STEP_EVENT_STARTED, 1])
        except Exception:
            return None
        return None

    def on_user_resolved(
        self,
        *,
        run_id: str,
        event,
        user_pk: Any,
        is_found: bool,
    ) -> None:
        try:
            self._append_step(
                run_id=run_id,
                step=[self.STEP_USER_RESOLVED, int(is_found)],
            )
        except Exception:
            return None
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
        try:
            self._append_step(
                run_id=run_id,
                step=[self.STEP_CONDITION_CHECKED, condition.pk, int(is_satisfied)],
            )
        except Exception:
            return None
        return None

    def on_action_performed(
        self,
        *,
        run_id: str,
        trigger,
        user_pk: Any,
        action,
    ) -> None:
        try:
            self._append_step(
                run_id=run_id,
                step=[self.STEP_ACTION_PERFORMED, action.pk, 1],
            )
        except Exception:
            return None
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
        try:
            self._append_step(
                run_id=run_id,
                step=[
                    self.STEP_ACTION_PERFORMED,
                    action.pk,
                    0,
                    error.__class__.__name__,
                ],
            )
        except Exception:
            return None
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
        try:
            TriggerExecutionLog.objects.filter(run_id=run_id).update(
                status=result,
                finished_at=timezone.now(),
            )
        except Exception:
            return None
        return None
