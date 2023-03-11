from typing import List, Optional

from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from model_bakery import baker
import pytest

from tests.app.models import SendEmailAction, Task, TaskCompletedEvent
from tests.utils import run_on_commit
from triggers.models import ActionCountCondition, Activity, Trigger


@pytest.fixture
def user() -> User:
    return baker.make(User, first_name='Bob', email='bob@example.com')


@pytest.fixture(params=[True, False])
def is_trigger_enabled(request) -> bool:
    return request.param


@pytest.fixture(autouse=True)
def trigger(is_trigger_enabled: bool) -> Trigger:
    trigger = baker.make(Trigger, is_enabled=is_trigger_enabled, name='First Completed Task Notification')
    baker.make(TaskCompletedEvent, trigger=trigger)
    # In order to notify the user once only, limit the number of performing with `ActionCountCondition`
    baker.make(ActionCountCondition, trigger=trigger, limit=1)
    baker.make(
        SendEmailAction,
        trigger=trigger,
        subject='Your First Task Completed!',
        message=(
            'Hey {{ user.first_name|capfirst }},\n'
            'You just completed your first task, keep it that way!'
        ),
    )
    return trigger


@pytest.fixture(params=[True, False])
def is_notification_already_sent(request) -> bool:
    return request.param


@pytest.fixture(autouse=True)
def activity(trigger: Trigger, is_notification_already_sent, user) -> Optional[Activity]:
    if is_notification_already_sent:
        return baker.make(Activity, trigger=trigger, user=user, action_count=1)
    return None


@pytest.fixture
def task(user: User) -> Task:
    return baker.make(Task, user=user)


def _get_action_count(user: User) -> int:
    return sum([activity.action_count for activity in user.trigger_activities.all()])


@pytest.mark.django_db
def test_notification(
    is_trigger_enabled: bool,
    is_notification_already_sent: bool,
    task: Task,
    mailoutbox: List[EmailMessage],
    user: User,
):
    initial_action_count = _get_action_count(user)
    task.complete()
    run_on_commit()
    if is_trigger_enabled and not is_notification_already_sent:
        email: EmailMessage = mailoutbox[0]
        assert email.to == [user.email]
        assert user.first_name in email.body
        assert _get_action_count(user) == initial_action_count + 1
    else:
        assert not mailoutbox
        assert _get_action_count(user) == initial_action_count
