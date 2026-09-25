"""Shared test fixtures.

By default every test runs as a fixed signed-in user so route tests don't need real Clerk tokens.
Mark a test/class with @pytest.mark.real_auth to exercise the real get_current_user dependency.
"""

from __future__ import annotations

import pytest

from backend.auth import CurrentUser, get_current_user
from backend.main import app
from backend.rate_limit import ai_generation_limiter

DEFAULT_TEST_USER = CurrentUser(id="test_user_default", email="tester@example.com", role="user")


def pytest_configure(config):
    config.addinivalue_line("markers", "real_auth: run without the signed-in test user override")


class SignedInAs:
    """Mutable holder so a test can switch which user the API sees mid-test."""

    def __init__(self, user: CurrentUser):
        self.user = user

    def __call__(self) -> CurrentUser:
        return self.user


@pytest.fixture(autouse=True)
def signed_in_user(request):
    ai_generation_limiter.reset()
    if request.node.get_closest_marker("real_auth"):
        yield None
        return
    holder = SignedInAs(DEFAULT_TEST_USER)
    app.dependency_overrides[get_current_user] = holder
    yield holder
    app.dependency_overrides.pop(get_current_user, None)
