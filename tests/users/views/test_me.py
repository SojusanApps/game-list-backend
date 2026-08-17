"""Tests for the GET /api/user/users/me/ action."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_me_returns_the_callers_own_account(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A brand-new Keycloak registrant's very first request to /users/me/ returns their own account."""
    token = make_keycloak_token(sub="12121212-1212-1212-1212-121212121212", nickname="me_endpoint_user")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-me"))

    assert response.status_code == status.HTTP_200_OK
    user = User.objects.get(keycloak_id="12121212-1212-1212-1212-121212121212")
    assert response.json()["id"] == user.pk
    assert response.json()["username"] == "me_endpoint_user"


@pytest.mark.django_db()
def test_me_rejects_unauthenticated_caller(api_client: APIClient) -> None:
    """No token, no access."""
    response = api_client.get(reverse("users:users-me"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
