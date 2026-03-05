from django.contrib.auth.models import User
from django.test import override_settings
from model_bakery import baker
import pytest

from tests.app.models import SendEmailAction, Task, TaskCompletedEvent
from tests.utils import run_on_commit
from triggers.contrib.logging.models import TriggerExecutionLog
from triggers.models import ActionCountCondition, Trigger


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

    execution_log = TriggerExecutionLog.objects.get()
    assert execution_log.user == user
    assert execution_log.trigger == trigger
    assert execution_log.status == TriggerExecutionLog.STATUS_SUCCESS
    assert execution_log.steps
    assert any(step[0] == 3 for step in execution_log.steps)
    assert any(step[0] == 4 and step[2] == 1 for step in execution_log.steps)


@pytest.mark.django_db()
@override_settings(TRIGGERS_EXECUTION_LOGGING_ENABLED=True)
def test_execution_log_created_for_missing_user(trigger: Trigger):
    event = trigger.events.instance_of(TaskCompletedEvent).first()
    assert event

    event.handle(
        user_pk=999999,
        trace_id='f' * 32,
    )

    execution_log = TriggerExecutionLog.objects.get(run_id='f' * 32)
    assert execution_log.status == TriggerExecutionLog.STATUS_USER_NOT_FOUND
    assert any(step[0] == 2 and step[1] == 0 for step in execution_log.steps)


@pytest.mark.django_db()
@override_settings(TRIGGERS_EXECUTION_LOGGING_ENABLED=False)
def test_execution_logs_not_created_when_disabled(user: User, trigger: Trigger):
    task = baker.make(Task, user=user, is_important=True)

    task.complete()
    run_on_commit()

    assert not TriggerExecutionLog.objects.exists()
