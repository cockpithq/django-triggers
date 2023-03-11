import datetime
from typing import List, Optional

from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from model_bakery import baker
import pytest

from tests.app.models import ClockEvent, HasUncompletedTaskCondition, SendEmailAction, Task
from tests.app.tasks import clock
from tests.utils import run_on_commit
from triggers.models import ActionFrequencyCondition, Activity, Trigger

MIN_FREQUENCY = datetime.timedelta(days=1)


@pytest.fixture(params=[True, False])
def is_trigger_enabled(request) -> bool:
    return request.param


@pytest.fixture(params=[True, False])
def is_reminder_already_sent(request) -> bool:
    return request.param


@pytest.fixture(params=[True, False])
def has_uncompleted_task(request) -> bool:
    return request.param


@pytest.fixture
def user() -> User:
    user = baker.make(User, first_name='Bob', email='bob@example.com')
    baker.make(Task, user=user, is_completed=True)
    return user


@pytest.fixture
def uncompleted_tasks(user, has_uncompleted_task) -> List[Task]:
    if has_uncompleted_task:
        return baker.make(Task, user=user, is_completed=False, _quantity=2)
    return []


@pytest.fixture(autouse=True)
def trigger(is_trigger_enabled: bool) -> Trigger:
    trigger = baker.make(Trigger, is_enabled=is_trigger_enabled, name='Uncompleted Task Reminder')
    baker.make(ClockEvent, trigger=trigger)
    baker.make(HasUncompletedTaskCondition, trigger=trigger)
    # Remind about the tasks no more often than `MIN_FREQUENCY`
    baker.make(ActionFrequencyCondition, trigger=trigger, limit=MIN_FREQUENCY)
    baker.make(
        SendEmailAction,
        trigger=trigger,
        subject='You have uncompleted tasks!',
        message=(
            'Hey {{ user.first_name|capfirst }},\n'
            'There are tasks you not completed yet: {{ tasks }}'
        ),
    )
    return trigger


@pytest.fixture(autouse=True)
def activity(trigger: Trigger, is_reminder_already_sent, user) -> Optional[Activity]:
    if is_reminder_already_sent:
        return baker.make(
            Activity,
            trigger=trigger,
            user=user,
            last_action_datetime=datetime.datetime.now() - MIN_FREQUENCY + datetime.timedelta(seconds=30),
        )
    return None


@pytest.mark.django_db
def test_reminder(
    is_trigger_enabled: bool,
    is_reminder_already_sent: bool,
    uncompleted_tasks: List[Task],
    mailoutbox: List[EmailMessage],
    user: User,
):
    clock()
    run_on_commit()
    if is_trigger_enabled and not is_reminder_already_sent and uncompleted_tasks:
        email: EmailMessage = mailoutbox[0]
        assert email.to == [user.email]
        assert user.first_name in email.body
        for task in uncompleted_tasks:
            assert task.name in email.body
    else:
        assert not mailoutbox
