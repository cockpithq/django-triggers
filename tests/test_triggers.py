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
    'execution_count,execution_number_limit,should_be_executed',
    ((0, 1, True), (1, 1, False), (1, 2, True), (1, None, True), (2, 1, False)),
)
def test_trigger_number_limit(
    user,
    app_session_started_trigger: Trigger,
    execution_count: int,
    execution_number_limit: Optional[int],
    should_be_executed: bool,
):
    app_session_started_trigger.number_limit = execution_number_limit
    app_session_started_trigger.save()
    if execution_count:
        user.trigger_activities.update_or_create(
            trigger=app_session_started_trigger,
            defaults={'execution_count': execution_count},
        )
    user.app_sessions.create(app=AppSession.APP_MOBILE)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    if should_be_executed:
        assert message
        assert user.trigger_activities.filter(
            trigger=app_session_started_trigger,
            execution_count=execution_count + 1,
        ).exists()
    else:
        assert not message
        assert user.trigger_activities.filter(
            trigger=app_session_started_trigger,
            execution_count=execution_count,
        ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'time_since_last_execution,execution_frequency_limit,should_be_executed',
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
    time_since_last_execution: Optional[datetime.timedelta],
    execution_frequency_limit: Optional[datetime.timedelta],
    should_be_executed: bool,
):
    app_session_started_trigger.frequency_limit = execution_frequency_limit
    app_session_started_trigger.save()
    if time_since_last_execution:
        last_execution_datetime = timezone.now() - time_since_last_execution
    else:
        last_execution_datetime = None
    if last_execution_datetime:
        user.trigger_activities.update_or_create(
            trigger=app_session_started_trigger,
            defaults={'last_execution_datetime': last_execution_datetime},
        )
    user.app_sessions.create(app=AppSession.APP_MOBILE)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    if should_be_executed:
        assert message
        if last_execution_datetime:
            assert user.trigger_activities.filter(
                trigger=app_session_started_trigger,
                last_execution_datetime__gt=last_execution_datetime,
            ).exists()
        else:
            assert user.trigger_activities.filter(
                trigger=app_session_started_trigger,
                last_execution_datetime__isnull=False,
            ).exists()
    else:
        assert not message
        assert user.trigger_activities.filter(
            trigger=app_session_started_trigger,
            last_execution_datetime=last_execution_datetime,
        ).exists()
