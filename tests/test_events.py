from django.contrib.auth.models import User
from model_bakery import baker
import pytest

from tests.app.models import AppSession, AppSessionStartedEvent
from tests.utils import run_on_commit


@pytest.fixture()
def desired_app() -> str:
    return AppSession.APP_MOBILE


@pytest.fixture()
def another_app(desired_app) -> str:
    return [app for (app, app_title) in AppSession.APP_CHOICES if app != desired_app][0]


@pytest.fixture(autouse=True)
def app_session_started_event(app_session_started_trigger, desired_app) -> AppSessionStartedEvent:
    return baker.make(AppSessionStartedEvent, trigger=app_session_started_trigger, app=desired_app)


@pytest.mark.django_db
def test_event_should_be_fired(user: User, desired_app: str, app_session_started_event: AppSessionStartedEvent):
    user.app_sessions.create(app=desired_app)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    assert message
    assert user.first_name.capitalize() in message.text
    assert app_session_started_event.app in message.text


@pytest.mark.django_db
def test_event_should_not_be_fired(user: User, another_app: str):
    user.app_sessions.create(app=another_app)
    assert not user.messages.all().count()
    run_on_commit()
    assert not user.messages.exists()
