from django.contrib.auth.models import User
from model_bakery import baker
import pytest

from tests.app.models import AppSession, AppSessionCountCondition, AppSessionStartedEvent
from tests.utils import run_on_commit
from triggers.models import Trigger


@pytest.fixture()
def desired_app() -> str:
    return AppSession.APP_MOBILE


@pytest.fixture()
def another_app(desired_app) -> str:
    return [app for (app, app_title) in AppSession.APP_CHOICES if app != desired_app][0]


@pytest.fixture(autouse=True)
def initial_app_session_condition(app_session_started_trigger: Trigger, desired_app: str) -> AppSessionCountCondition:
    return baker.make(
        AppSessionCountCondition,
        trigger=app_session_started_trigger,
        app=desired_app,
        count=1,
    )


@pytest.fixture
def app_session(user: User, desired_app: str) -> AppSession:
    return baker.make(AppSession, user=user, app=desired_app)


@pytest.mark.django_db
def test_condition_is_satisfied(
    user: User,
    app_session_started_event: AppSessionStartedEvent,
    desired_app: str,
):
    user.app_sessions.create(app=desired_app)
    assert not user.messages.all().count()
    run_on_commit()
    message = user.messages.first()
    assert message


@pytest.mark.django_db
def test_condition_is_not_satisfied(user: User, desired_app: str, app_session: AppSession):
    user.app_sessions.create(app=desired_app)
    assert not user.messages.all().count()
    run_on_commit()
    assert not user.messages.exists()
