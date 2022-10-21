from django.contrib.auth.models import User
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
