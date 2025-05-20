import uuid
from contextlib import contextmanager

import pytest
from django.contrib.auth import get_user_model

from triggers.models import (
    Action,
    Activity,
    Condition,
    Event,
    Trigger,
    TriggerLog,
    log_trigger_event,
)
from triggers.tasks import handle_event

User = get_user_model()


@pytest.fixture
def trigger():
    return Trigger.objects.create(name="Edge Trigger", is_enabled=True)


@pytest.fixture
def event(trigger):
    return Event.objects.create(trigger=trigger)


@pytest.mark.django_db
def test_log_trigger_event_missing_trigger():
    class Dummy:
        pk = 1
        trigger_id = 0

    dummy = Dummy()
    assert log_trigger_event(dummy, "event", "fire") is None


@pytest.mark.django_db
def test_get_entity_object_import_error(trigger, event):
    run_id = log_trigger_event(event, "event", stage="fire")
    log = TriggerLog.objects.get(run_id=run_id)
    log.entity_class_path = "does.not.Exist"
    log.save(update_fields=["entity_class_path"])
    assert log.get_entity_object() is None


@pytest.mark.django_db
def test_get_entity_object_deleted(trigger, event):
    run_id = log_trigger_event(event, "event", stage="fire")
    log = TriggerLog.objects.get(run_id=run_id)
    event.delete()
    assert log.get_entity_object() is None


@pytest.mark.django_db
def test_activity_lock_cancel(user, trigger):
    with Activity.lock(user, trigger) as activity:
        raise Activity.Cancel()
    activity.refresh_from_db()
    assert activity.action_count == 0


@pytest.mark.django_db
def test_on_event_condition_unsatisfied(monkeypatch, user, trigger):
    Condition._default_manager.create(trigger=trigger)
    action = Action._default_manager.create(trigger=trigger)
    event = Event.objects.create(trigger=trigger)

    monkeypatch.setattr(Condition, "is_satisfied", lambda self, u: False)
    monkeypatch.setattr(Action, "perform", lambda self, u, c: (_ for _ in ()).throw(AssertionError))

    trigger.on_event(user, {})

    log = TriggerLog.objects.filter(entity_type="trigger", stage="condition_check").last()
    assert log.result is False


@pytest.mark.django_db
def test_on_event_action_exception_logged(monkeypatch, user, trigger):
    action = Action._default_manager.create(trigger=trigger)

    def failing(self, user, ctx):
        raise ValueError("boom")

    monkeypatch.setattr(Action, "perform", failing)

    @contextmanager
    def no_lock(u, t):
        yield Activity(trigger=t, user=u)

    monkeypatch.setattr(Activity, "lock", no_lock)

    with pytest.raises(ValueError):
        trigger.on_event(user, {})

    log = TriggerLog.objects.filter(entity_type="action", stage="action_perform", result=False).last()
    assert "boom" in log.details["error"]


@pytest.mark.django_db
def test_handle_event_error_logging(monkeypatch, user, trigger):
    event = Event.objects.create(trigger=trigger)

    def failing_handle(self, user_pk, **ctx):
        raise RuntimeError("oops")

    monkeypatch.setattr(Event, "handle", failing_handle)

    with pytest.raises(RuntimeError):
        handle_event(event.pk, user.pk, _run_id=str(uuid.uuid4()))

    log = TriggerLog.objects.filter(entity_type="event", stage="handle_start", result=False).last()
    assert "oops" in log.details["error"]
