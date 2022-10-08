import datetime
from typing import Optional

from django.contrib.auth.models import User
from django.utils import timezone
import pytest

from tests.app.models import AppSession
from tests.utils import run_on_commit
from triggers.models import Trigger


@pytest.mark.django_db
@pytest.mark.parametrize('is_enabled', [True, False])
def test_trigger_is_enabled(user: User, app_session_started_trigger: Trigger, is_enabled):
    app_session_started_trigger.is_enabled = is_enabled
    app_session_started_trigger.save()
    user.app_sessions.create(app=AppSession.APP_MOBILE)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    if is_enabled:
        assert message
    else:
        assert not message


@pytest.mark.django_db
@pytest.mark.parametrize(
    'action_count,action_count_limit,should_be_performed',
    ((0, 1, True), (1, 1, False), (1, 2, True), (1, None, True), (2, 1, False)),
)
def test_trigger_action_count_limit(
    user,
    app_session_started_trigger: Trigger,
    action_count: int,
    action_count_limit: Optional[int],
    should_be_performed: bool,
):
    app_session_started_trigger.action_count_limit = action_count_limit
    app_session_started_trigger.save()
    if action_count:
        user.trigger_activities.update_or_create(
            trigger=app_session_started_trigger,
            defaults={'action_count': action_count},
        )
    user.app_sessions.create(app=AppSession.APP_MOBILE)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    if should_be_performed:
        assert message
        assert user.trigger_activities.filter(
            trigger=app_session_started_trigger,
            action_count=action_count + 1,
        ).exists()
    else:
        assert not message
        assert user.trigger_activities.filter(
            trigger=app_session_started_trigger,
            action_count=action_count,
        ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'time_since_last_action,action_frequency_limit,should_be_performed',
    (
        (datetime.timedelta(seconds=1), datetime.timedelta(seconds=1), True),
        (datetime.timedelta(seconds=1), datetime.timedelta(seconds=10), False),
        (None, datetime.timedelta(seconds=1), True),
        (None, None, True),
    ),
)
def test_trigger_frequency_limit(
    user,
    app_session_started_trigger: Trigger,
    time_since_last_action: Optional[datetime.timedelta],
    action_frequency_limit: Optional[datetime.timedelta],
    should_be_performed: bool,
):
    app_session_started_trigger.action_frequency_limit = action_frequency_limit
    app_session_started_trigger.save()
    if time_since_last_action:
        last_action_datetime = timezone.now() - time_since_last_action
    else:
        last_action_datetime = None
    if last_action_datetime:
        user.trigger_activities.update_or_create(
            trigger=app_session_started_trigger,
            defaults={'last_action_datetime': last_action_datetime},
        )
    user.app_sessions.create(app=AppSession.APP_MOBILE)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    if should_be_performed:
        assert message
        if last_action_datetime:
            assert user.trigger_activities.filter(
                trigger=app_session_started_trigger,
                last_action_datetime__gt=last_action_datetime,
            ).exists()
        else:
            assert user.trigger_activities.filter(
                trigger=app_session_started_trigger,
                last_action_datetime__isnull=False,
            ).exists()
    else:
        assert not message
        assert user.trigger_activities.filter(
            trigger=app_session_started_trigger,
            last_action_datetime=last_action_datetime,
        ).exists()
