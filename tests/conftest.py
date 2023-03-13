from django.contrib.auth.models import User
from model_bakery import baker
import pytest


@pytest.fixture()
def user() -> User:
    return baker.make(User, first_name='Bob')
