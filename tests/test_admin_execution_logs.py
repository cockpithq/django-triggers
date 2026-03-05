from django.contrib.auth.models import User
from django.urls import reverse
from model_bakery import baker
import pytest

from triggers.contrib.logging.models import TriggerExecutionLog
from triggers.models import Trigger


@pytest.mark.django_db()
def test_execution_logs_action_renders_email_form(admin_client):
    trigger = baker.make(Trigger, name="Execution Timeline Trigger")

    response = admin_client.post(
        reverse("admin:triggers_trigger_changelist"),
        {
            "action": "view_user_execution_logs",
            "_selected_action": [str(trigger.pk)],
        },
    )

    assert response.status_code == 200
    assert b'name="email"' in response.content


@pytest.mark.django_db()
def test_execution_logs_action_redirects_to_timeline(admin_client):
    trigger = baker.make(Trigger, name="Execution Timeline Trigger")

    response = admin_client.post(
        reverse("admin:triggers_trigger_changelist"),
        {
            "action": "view_user_execution_logs",
            "_selected_action": [str(trigger.pk)],
            "apply": "1",
            "email": "bob@example.com",
        },
    )

    assert response.status_code == 302
    assert "execution-logs/" in response["Location"]
    assert "email=bob%40example.com" in response["Location"]


@pytest.mark.django_db()
def test_execution_logs_timeline_displays_run(admin_client):
    trigger = baker.make(Trigger, name="Execution Timeline Trigger")
    user = baker.make(User, email="bob@example.com")
    execution_log = baker.make(
        TriggerExecutionLog,
        trigger=trigger,
        user=user,
        status=TriggerExecutionLog.STATUS_SUCCESS,
        run_id="f" * 32,
        steps=[
            [1, 1, 1700000000000],
            [2, 1, 1700000000100],
            [3, 100, 1, 1700000000200],
            [4, 200, 1, 1700000000400],
        ],
    )

    response = admin_client.get(
        reverse("admin:triggers_trigger_execution_logs"),
        {
            "trigger_id": str(trigger.pk),
            "email": user.email,
        },
    )

    assert response.status_code == 200
    assert execution_log.run_id.encode() in response.content
    assert b"Event handling started" in response.content
    assert b"+100 ms" in response.content
    assert b"background:" in response.content