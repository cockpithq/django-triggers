from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from model_bakery import baker
import pytest

from tests.app.models import SendEmailAction, Task, TaskCompletedEvent
from tests.utils import run_on_commit
from triggers.contrib.logging.models import TriggerRun
from triggers.models import ActionCountCondition, Activity, Trigger


@pytest.fixture()
def user() -> User:
    return baker.make(User, first_name='Bob', email='bob@example.com')


@pytest.fixture()
def trigger() -> Trigger:
    trigger = baker.make(Trigger, is_enabled=True, name='Execution Log Trigger')
    baker.make(TaskCompletedEvent, trigger=trigger, important_only=True)
    baker.make(ActionCountCondition, trigger=trigger, limit=1)
    baker.make(
        SendEmailAction,
        trigger=trigger,
        subject='Important Task Completed',
        message='Hey {{ user.first_name|capfirst }}',
    )
    return trigger


@pytest.mark.django_db()
@override_settings(TRIGGERS_EXECUTION_LOGGING_ENABLED=True)
def test_execution_log_created_for_successful_run(user: User, trigger: Trigger):
    task = baker.make(Task, user=user, is_important=True)

    task.complete()
    run_on_commit()

    execution_log = TriggerRun.objects.get()
    assert execution_log.user == user
    assert execution_log.trigger == trigger
    assert execution_log.status == TriggerRun.STATUS_SUCCEEDED
    assert execution_log.steps
    assert any(step[0] == 3 for step in execution_log.steps)
    assert any(step[0] == 4 and step[2] == 1 for step in execution_log.steps)
    assert all(isinstance(step[-1], int) for step in execution_log.steps)


@pytest.mark.django_db()
@override_settings(TRIGGERS_EXECUTION_LOGGING_ENABLED=True)
def test_execution_log_created_for_missing_user(trigger: Trigger):
    event = trigger.events.instance_of(TaskCompletedEvent).first()
    assert event

    event.handle(
        user_pk=999999,
        run_id='f' * 32,
    )

    execution_log = TriggerRun.objects.get(run_id='f' * 32)
    assert execution_log.status == TriggerRun.STATUS_SKIPPED
    assert any(step[0] == 2 and step[1] == 0 for step in execution_log.steps)


@pytest.mark.django_db()
@override_settings(TRIGGERS_EXECUTION_LOGGING_ENABLED=False)
def test_execution_logs_not_created_when_disabled(user: User, trigger: Trigger):
    task = baker.make(Task, user=user, is_important=True)

    task.complete()
    run_on_commit()

    assert not TriggerRun.objects.exists()


@pytest.mark.django_db()
@override_settings(TRIGGERS_EXECUTION_LOGGING_ENABLED=True)
def test_execution_log_created_when_action_fails(user: User):
    trigger = baker.make(Trigger, is_enabled=True, name='Failing Action Trigger')
    baker.make(TaskCompletedEvent, trigger=trigger, important_only=True)
    action = baker.make(SendEmailAction, trigger=trigger, subject='Test', message='Test')
    task = baker.make(Task, user=user, is_important=True)

    with patch.object(action, 'perform', side_effect=ValueError("Action failed")):
        task.complete()
        run_on_commit()

    execution_log = TriggerRun.objects.get()
    execution_log.refresh_from_db()
    assert execution_log.user == user
    assert execution_log.trigger == trigger
    assert execution_log.status == TriggerRun.STATUS_ACTION_FAILED
    assert any(step[0] == 4 and step[2] == 0 for step in execution_log.steps)
    assert any("ValueError" in str(step) for step in execution_log.steps if len(step) > 3)


@pytest.mark.django_db()
@override_settings(TRIGGERS_EXECUTION_LOGGING_ENABLED=True)
def test_execution_log_created_when_conditions_fail(user: User):
    trigger = baker.make(Trigger, is_enabled=True, name='Failing Condition Trigger')
    baker.make(TaskCompletedEvent, trigger=trigger, important_only=True)
    condition = baker.make(ActionCountCondition, trigger=trigger, limit=1)
    baker.make(SendEmailAction, trigger=trigger, subject='Test', message='Test')
    task = baker.make(Task, user=user, is_important=True)

    with patch.object(condition, 'is_satisfied', return_value=False):
        task.complete()
        run_on_commit()

    execution_log = TriggerRun.objects.get()
    execution_log.refresh_from_db()
    assert execution_log.user == user
    assert execution_log.trigger == trigger
    assert execution_log.status == TriggerRun.STATUS_CONDITIONS_FAILED
    assert any(step[0] == 3 and step[2] == 0 for step in execution_log.steps)


@pytest.mark.django_db()
def test_activity_str(user: User):
    trigger = baker.make(Trigger, name='Test Trigger')
    activity = baker.make(Activity, trigger=trigger, user=user)
    assert str(activity) == f'{trigger} - {user}'
