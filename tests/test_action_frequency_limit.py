import datetime
from typing import Optional

from django.utils import timezone
from model_bakery import baker
import pytest

from tests.app.models import AppSession
from tests.utils import run_on_commit
from triggers.models import ActionFrequencyCondition, Activity, Trigger


@pytest.fixture(autouse=True)
def action_frequency_condition(app_session_started_trigger: Trigger) -> ActionFrequencyCondition:
    return baker.make(
        ActionFrequencyCondition,
        trigger=app_session_started_trigger,
        limit=datetime.timedelta(seconds=3),
    )


@pytest.fixture(params=[None, datetime.timedelta(seconds=1), datetime.timedelta(seconds=5)])
def time_since_last_action(request) -> Optional[datetime.timedelta]:
    return request.param


@pytest.fixture(autouse=True)
def activity(
    app_session_started_trigger: Trigger,
    time_since_last_action: Optional[datetime.timedelta],
    user,
) -> Optional[Activity]:
    if time_since_last_action is not None:
        return baker.make(
            Activity,
            trigger=app_session_started_trigger,
            user=user,
            last_action_datetime=timezone.now() - time_since_last_action,
        )
    return None


@pytest.mark.django_db
def test_trigger_frequency_limit(
    user,
    app_session_started_trigger: Trigger,
    time_since_last_action: Optional[datetime.timedelta],
    action_frequency_condition: ActionFrequencyCondition,
    activity: Optional[Activity],
):
    user.app_sessions.create(app=AppSession.APP_MOBILE)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    should_be_performed = time_since_last_action is None or time_since_last_action >= action_frequency_condition.limit
    if should_be_performed:
        assert message
        if activity:
            assert user.trigger_activities.filter(
                trigger=app_session_started_trigger,
                last_action_datetime__gt=activity.last_action_datetime,
            ).exists()
        else:
            assert user.trigger_activities.filter(
                trigger=app_session_started_trigger,
                last_action_datetime__isnull=False,
            ).exists()
    else:
        assert not message
        if activity:
            assert user.trigger_activities.filter(
                trigger=app_session_started_trigger,
                last_action_datetime=activity.last_action_datetime,
            ).exists()
