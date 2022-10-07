from django.contrib.auth.models import User
from model_bakery import baker
import pytest

from tests.app.models import AppSessionStartedEvent, SendMessageAction
from triggers.models import Trigger


@pytest.fixture()
def user() -> User:
    return baker.make(User, first_name='Bob')


@pytest.fixture()
def app_session_started_trigger() -> Trigger:
    return baker.make(Trigger, is_enabled=True)


@pytest.fixture(autouse=True)
def app_session_started_event(app_session_started_trigger: Trigger) -> AppSessionStartedEvent:
    return baker.make(AppSessionStartedEvent, trigger=app_session_started_trigger, app='')


@pytest.fixture(autouse=True)
def app_session_started_action(app_session_started_trigger: Trigger) -> SendMessageAction:
    return baker.make(
        SendMessageAction,
        trigger=app_session_started_trigger,
        text='Hi {{ user.first_name | capfirst }}! Welcome to our {{ app }} app.',
    )
