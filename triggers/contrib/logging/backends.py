from typing import Any, Mapping

from django.conf import settings
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.utils import timezone

from triggers.contrib.logging.models import TriggerExecutionLog
from triggers.signals import (
    action_failed,
    action_performed,
    condition_checked,
    event_enqueued,
    event_started,
    event_user_resolved,
    run_completed,
)

User = get_user_model()


STEP_EVENT_STARTED = 1
STEP_USER_RESOLVED = 2
STEP_CONDITION_CHECKED = 3
STEP_ACTION_PERFORMED = 4


def _is_enabled() -> bool:
    return bool(getattr(settings, "TRIGGERS_EXECUTION_LOGGING_ENABLED", True))


def _append_step(*, run_id: str, step):
    execution_log = TriggerExecutionLog.objects.filter(run_id=run_id).first()
    if not execution_log:
        return
    steps = list(execution_log.steps)
    steps.append(step)
    TriggerExecutionLog.objects.filter(pk=execution_log.pk).update(steps=steps)


def _get_or_create_log(
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


@receiver(event_enqueued)
def on_event_enqueued(sender, run_id: str, event, user_pk: Any, context: Mapping[str, Any], **kwargs):
    if not _is_enabled():
        return
    _get_or_create_log(run_id=run_id, event=event, user_pk=user_pk)


@receiver(event_started)
def on_event_started(sender, run_id: str, event, user_pk: Any, context: Mapping[str, Any], **kwargs):
    if not _is_enabled():
        return
    _get_or_create_log(run_id=run_id, event=event, user_pk=user_pk)
    TriggerExecutionLog.objects.filter(run_id=run_id).update(
        status=TriggerExecutionLog.STATUS_STARTED,
        started_at=timezone.now(),
    )
    _append_step(run_id=run_id, step=[STEP_EVENT_STARTED, 1])


@receiver(event_user_resolved)
def on_user_resolved(sender, run_id: str, event, user_pk: Any, is_found: bool, **kwargs):
    if not _is_enabled():
        return
    _append_step(
        run_id=run_id,
        step=[STEP_USER_RESOLVED, int(is_found)],
    )


@receiver(condition_checked)
def on_condition_checked(
    sender,
    run_id: str,
    trigger,
    user_pk: Any,
    condition,
    is_satisfied: bool,
    **kwargs,
):
    if not _is_enabled():
        return
    _append_step(
        run_id=run_id,
        step=[STEP_CONDITION_CHECKED, condition.pk, int(is_satisfied)],
    )


@receiver(action_performed)
def on_action_performed(sender, run_id: str, trigger, user_pk: Any, action, **kwargs):
    if not _is_enabled():
        return
    _append_step(
        run_id=run_id,
        step=[STEP_ACTION_PERFORMED, action.pk, 1],
    )


@receiver(action_failed)
def on_action_failed(
    sender,
    run_id: str,
    trigger,
    user_pk: Any,
    action,
    error: Exception,
    **kwargs,
):
    if not _is_enabled():
        return
    _append_step(
        run_id=run_id,
        step=[
            STEP_ACTION_PERFORMED,
            action.pk,
            0,
            error.__class__.__name__,
        ],
    )


@receiver(run_completed)
def on_run_completed(sender, run_id: str, event, trigger, user_pk: Any, result: str, **kwargs):
    if not _is_enabled():
        return
    TriggerExecutionLog.objects.filter(run_id=run_id).update(
        status=result,
        finished_at=timezone.now(),
    )
