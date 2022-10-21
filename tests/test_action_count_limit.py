from typing import Optional

from model_bakery import baker
import pytest

from tests.app.models import AppSession
from tests.utils import run_on_commit
from triggers.models import ActionCountCondition, Activity, Trigger


@pytest.fixture(params=[None, 1, 2, 3])
def action_count(request) -> Optional[int]:
    return request.param


@pytest.fixture(autouse=True)
def action_count_condition(app_session_started_trigger: Trigger) -> ActionCountCondition:
    return baker.make(ActionCountCondition, trigger=app_session_started_trigger, limit=2)


@pytest.fixture(autouse=True)
def activity(app_session_started_trigger: Trigger, action_count: Optional[int], user) -> Optional[Activity]:
    if action_count is not None:
        return baker.make(Activity, trigger=app_session_started_trigger, user=user, action_count=action_count)
    return None


@pytest.mark.django_db
def test_trigger_action_count_limit(
    user,
    app_session_started_trigger: Trigger,
    action_count: Optional[int],
    action_count_condition: ActionCountCondition,
    activity: Optional[Activity],
):
    user.app_sessions.create(app=AppSession.APP_MOBILE)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    should_be_performed = action_count is None or action_count < action_count_condition.limit
    if should_be_performed:
        assert message
        assert user.trigger_activities.filter(
            trigger=app_session_started_trigger,
            action_count=(action_count or 0) + 1,
        ).exists()
    else:
        assert not message
        assert user.trigger_activities.filter(
            trigger=app_session_started_trigger,
            action_count=action_count,
        ).exists()
