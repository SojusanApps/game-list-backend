"""Test for users middleware."""

import datetime
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status

from game_list.users.middleware import UpdateLastActivityMiddleware

if TYPE_CHECKING:
    from django.test import RequestFactory

User = get_user_model()


@pytest.fixture
def middleware() -> UpdateLastActivityMiddleware:
    """Fixture to create an instance of the UpdateLastActivityMiddleware."""

    def get_response(request: HttpRequest) -> HttpResponse:  # noqa: ARG001
        """A simple get_response function that returns a basic HttpResponse."""
        return HttpResponse("OK")

    return UpdateLastActivityMiddleware(get_response)


@pytest.mark.django_db()
def test_update_last_activity_middleware(middleware: UpdateLastActivityMiddleware, rf: RequestFactory) -> None:
    """Test that the UpdateLastActivityMiddleware correctly updates the last_active field of authenticated users."""
    cache.clear()
    user = User.objects.create_user(username="testuser", email="test@test.com", password="password")  # noqa: S106
    request = rf.get("/")
    request.user = user

    assert user.last_active is None

    # First request: should hit DB and set cache
    with freeze_time("2026-03-23 12:00:00"):
        response = middleware(request)
        user.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert user.last_active is not None
        assert user.last_active == timezone.now()

        # Cache key should be set
        cache_key = f"last_activity_{user.id}"
        assert cache.get(cache_key) == 1

    # Second request immediately after: should not hit DB
    with freeze_time("2026-03-23 12:02:00"):
        middleware(request)
        user.refresh_from_db()

        # Database value shouldn't change
        assert user.last_active == datetime.datetime(2026, 3, 23, 12, 0, 0, tzinfo=datetime.UTC)

    # Let cooldown expire
    cache.clear()
    # Alternatively simulate time lapse (if you change cache TTL or rely on real cache setup)

    with freeze_time("2026-03-23 12:06:00"):
        middleware(request)
        user.refresh_from_db()

        # Value SHOULD change because we effectively expired/cleared the cache
        assert user.last_active == timezone.now()
