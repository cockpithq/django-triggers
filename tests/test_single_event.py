from django.contrib.auth.models import User
from model_bakery import baker
import pytest

from tests.app.models import AppSession, AppSessionCountCondition, AppSessionStartedEvent, SendMessageAction
from tests.utils import run_on_commit
from triggers.models import Trigger


@pytest.fixture()
def user() -> User:
    return baker.make(User)


@pytest.fixture()
def trigger() -> Trigger:
    return baker.make(Trigger, is_enabled=True)


@pytest.fixture()
def desired_app() -> str:
    return AppSession.APP_MOBILE


@pytest.fixture()
def another_app(desired_app) -> str:
    return [app for (app, app_title) in AppSession.APP_CHOICES if app != desired_app][0]


@pytest.fixture(autouse=True)
def initial_app_session_condition(trigger: Trigger, desired_app) -> AppSessionCountCondition:
    return baker.make(AppSessionCountCondition, trigger=trigger, app=desired_app, count=1)


@pytest.fixture(autouse=True)
def app_session_started_event(trigger: Trigger, desired_app) -> AppSessionStartedEvent:
    return baker.make(AppSessionStartedEvent, trigger=trigger, app=desired_app)


@pytest.fixture(autouse=True)
def send_welcome_message_action(trigger: Trigger) -> SendMessageAction:
    return baker.make(
        SendMessageAction,
        trigger=trigger,
        text='Hi {{ user.first_name | capfirst }}! Welcome to our {{ app }} app.',
    )


@pytest.fixture
def app_session(user: User, desired_app: str) -> AppSession:
    return baker.make(AppSession, user=user, app=desired_app)


@pytest.mark.django_db
@pytest.mark.parametrize('is_trigger_enabled', (True, False))
def test_event_filter_is_matched_and_condition_is_satisfied(
    user: User,
    desired_app: str,
    trigger: Trigger,
    is_trigger_enabled: bool,
):
    trigger.is_enabled = is_trigger_enabled
    trigger.save()
    user.app_sessions.create(app=desired_app)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    if is_trigger_enabled:
        assert message
        assert user.first_name.capitalize() in message.text
        assert desired_app in message.text
        assert trigger.activities.filter(user=user, execution_count=1).exists()
    else:
        assert not message


@pytest.mark.django_db
def test_event_filter_is_not_matched(user: User, another_app: str):
    user.app_sessions.create(app=another_app)
    assert not user.messages.all().count()
    run_on_commit()
    assert not user.messages.exists()


@pytest.mark.django_db
def test_condition_is_not_satisfied(user: User, desired_app: str, app_session: AppSession):
    user.app_sessions.create(app=desired_app)
    assert not user.messages.all().count()
    run_on_commit()
    assert not user.messages.exists()
