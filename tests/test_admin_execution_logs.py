from django.contrib.auth.models import User
from django.urls import reverse
from model_bakery import baker
import pytest

from triggers.contrib.logging.models import TriggerRun
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
    assert f"trigger_ids={trigger.pk}" in response["Location"]
    assert "email=bob%40example.com" in response["Location"]


@pytest.mark.django_db()
def test_execution_logs_action_redirects_to_timeline_for_multiple_triggers(admin_client):
    trigger_1 = baker.make(Trigger, name="Execution Timeline Trigger A")
    trigger_2 = baker.make(Trigger, name="Execution Timeline Trigger B")

    response = admin_client.post(
        reverse("admin:triggers_trigger_changelist"),
        {
            "action": "view_user_execution_logs",
            "_selected_action": [str(trigger_1.pk), str(trigger_2.pk)],
            "apply": "1",
            "email": "bob@example.com",
        },
    )

    assert response.status_code == 302
    assert f"trigger_ids={trigger_1.pk}%2C{trigger_2.pk}" in response["Location"]


@pytest.mark.django_db()
def test_execution_logs_timeline_displays_run(admin_client):
    trigger = baker.make(Trigger, name="Execution Timeline Trigger")
    user = baker.make(User, email="bob@example.com")
    execution_log = baker.make(
        TriggerRun,
        trigger=trigger,
        user=user,
        status=TriggerRun.STATUS_SUCCEEDED,
        run_id="f" * 32,
        timeline=[
            [1, 1, 1700000000000],
            [2, 1, 1700000000100],
            [3, 1, None, 1700000000200],
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


@pytest.mark.django_db()
def test_execution_logs_timeline_displays_runs_for_multiple_triggers(admin_client):
    trigger_1 = baker.make(Trigger, name="Execution Timeline Trigger A")
    trigger_2 = baker.make(Trigger, name="Execution Timeline Trigger B")
    user = baker.make(User, email="bob@example.com")
    log_1 = baker.make(
        TriggerRun,
        trigger=trigger_1,
        user=user,
        status=TriggerRun.STATUS_SUCCEEDED,
        run_id="a" * 32,
        timeline=[[1, 1, 1700000000000]],
    )
    log_2 = baker.make(
        TriggerRun,
        trigger=trigger_2,
        user=user,
        status=TriggerRun.STATUS_ACTION_FAILED,
        run_id="b" * 32,
        timeline=[[1, 1, 1700000000100]],
    )

    response = admin_client.get(
        reverse("admin:triggers_trigger_execution_logs"),
        {
            "trigger_ids": f"{trigger_1.pk},{trigger_2.pk}",
            "email": user.email,
        },
    )

    assert response.status_code == 200
    assert log_1.run_id.encode() in response.content
    assert log_2.run_id.encode() in response.content
    assert trigger_1.name.encode() in response.content
    assert trigger_2.name.encode() in response.content


@pytest.mark.django_db()
def test_execution_logs_timeline_is_paginated_by_50(admin_client):
    trigger = baker.make(Trigger, name="Execution Timeline Trigger")
    user = baker.make(User, email="bob@example.com")
    run_ids = []
    for idx in range(55):
        run_id = f"{idx:032d}"
        run_ids.append(run_id)
        baker.make(
            TriggerRun,
            trigger=trigger,
            user=user,
            status=TriggerRun.STATUS_SUCCEEDED,
            run_id=run_id,
            timeline=[[1, 1, 1700000000000 + idx]],
        )

    first_page_response = admin_client.get(
        reverse("admin:triggers_trigger_execution_logs"),
        {
            "trigger_id": str(trigger.pk),
            "email": user.email,
        },
    )

    assert first_page_response.status_code == 200
    assert b"Page 1 of 2" in first_page_response.content
    assert run_ids[-1].encode() in first_page_response.content
    assert run_ids[0].encode() not in first_page_response.content

    second_page_response = admin_client.get(
        reverse("admin:triggers_trigger_execution_logs"),
        {
            "trigger_id": str(trigger.pk),
            "email": user.email,
            "page": "2",
        },
    )

    assert second_page_response.status_code == 200
    assert b"Page 2 of 2" in second_page_response.content
    assert run_ids[0].encode() in second_page_response.content
