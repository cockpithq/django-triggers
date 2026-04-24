from typing import Any

from django.conf import settings
from django.dispatch import receiver
from django.utils import timezone

from triggers.constants import TriggerOutcome
from triggers.contrib.logging.models import TriggerRun
from triggers.models import Action, Condition, Event

_OUTCOME_TO_STATUS = {
    TriggerOutcome.SUCCEEDED: TriggerRun.STATUS_SUCCEEDED,
    TriggerOutcome.ACTION_FAILED: TriggerRun.STATUS_ACTION_FAILED,
    TriggerOutcome.SKIPPED_FOR_INSTANCE: TriggerRun.STATUS_SKIPPED,
    TriggerOutcome.SKIPPED_FOR_QUERYSET: TriggerRun.STATUS_CONDITIONS_FAILED,
}

STEP_EVENT_STARTED = 1
STEP_USER_RESOLVED = 2
STEP_CONDITION_CHECKED = 3
STEP_ACTION_PERFORMED = 4


def _is_enabled() -> bool:
    return bool(getattr(settings, "TRIGGERS_EXECUTION_LOGGING_ENABLED", True))


@receiver(Event.fired)
def on_event_fired(
    sender,
    event,
    run_id: str,
    user_pk: Any,
    **kwargs,
):
    if not _is_enabled():
        return
    TriggerRun.objects.for_run_id(
        run_id=run_id,
        event=event,
        user_pk=user_pk,
    )


@receiver(Event.received)
def on_event_received(
    sender,
    event,
    run_id: str,
    user_pk: Any,
    **kwargs,
):
    if not _is_enabled():
        return
    TriggerRun.objects.for_run_id(
        run_id=run_id,
        event=event,
        user_pk=user_pk,
    )
    TriggerRun.objects.filter(run_id=run_id).update(
        status=TriggerRun.STATUS_STARTED,
        started_at=timezone.now(),
    )
    execution_log = TriggerRun.objects.filter(run_id=run_id).first()
    if execution_log:
        execution_log.append_step([STEP_EVENT_STARTED, 1])


@receiver(Event.user_resolved)
def on_user_resolved(sender, run_id: str, event, user_pk: Any, is_found: bool, **kwargs):
    if not _is_enabled():
        return
    execution_log = TriggerRun.objects.filter(run_id=run_id).first()
    if execution_log:
        execution_log.append_step([STEP_USER_RESOLVED, int(is_found)])


@receiver(Condition.checked)
def on_condition_checked(
    sender,
    event,
    run_id: str,
    trigger,
    user_pk: Any,
    is_satisfied: bool,
    failed_condition,
    **kwargs,
):
    if not _is_enabled():
        return
    execution_log = TriggerRun.objects.filter(run_id=run_id).first()
    if execution_log:
        failed_pk = failed_condition.pk if failed_condition is not None else None
        execution_log.append_step([STEP_CONDITION_CHECKED, int(is_satisfied), failed_pk])


@receiver(Action.performed)
def on_action_performed(sender, run_id: str, trigger, user_pk: Any, action, **kwargs):
    if not _is_enabled():
        return
    execution_log = TriggerRun.objects.filter(run_id=run_id).first()
    if execution_log:
        execution_log.append_step([STEP_ACTION_PERFORMED, action.pk, 1])


@receiver(Action.failed)
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
    execution_log = TriggerRun.objects.filter(run_id=run_id).first()
    if execution_log:
        execution_log.append_step([
            STEP_ACTION_PERFORMED,
            action.pk,
            0,
            error.__class__.__name__,
        ])


@receiver(Event.handled)
def on_event_handled(
    sender,
    event,
    run_id: str,
    trigger,
    user_pk: Any,
    trigger_outcome: TriggerOutcome,
    **kwargs,
):
    if not _is_enabled():
        return
    status = _OUTCOME_TO_STATUS[trigger_outcome]
    TriggerRun.objects.filter(run_id=run_id).update(
        status=status,
        finished_at=timezone.now(),
    )
