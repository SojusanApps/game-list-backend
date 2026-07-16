"""Tests for the change-password action on UserViewSet."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_change_password_unauthenticated(api_client: APIClient) -> None:
    """An unauthenticated request is rejected."""
    response = api_client.post(
        reverse("users:users-change-password"),
        {
            "current_password": "test",
            "new_password": "a-much-stronger-password-123",
            "new_password_confirm": "a-much-stronger-password-123",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_change_password_rejects_wrong_current_password(authenticated_api_client: APIClient) -> None:
    """An incorrect current_password is rejected."""
    response = authenticated_api_client.post(
        reverse("users:users-change-password"),
        {
            "current_password": "wrong-password",
            "new_password": "a-much-stronger-password-123",
            "new_password_confirm": "a-much-stronger-password-123",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_change_password_rejects_mismatched_confirmation(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """new_password and new_password_confirm must match."""
    user_fixture.set_password("test")
    user_fixture.save()

    response = authenticated_api_client.post(
        reverse("users:users-change-password"),
        {
            "current_password": "test",
            "new_password": "a-much-stronger-password-123",
            "new_password_confirm": "a-different-password-456",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_change_password_rejects_weak_new_password(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A new_password failing Django's password validators is rejected."""
    user_fixture.set_password("test")
    user_fixture.save()

    response = authenticated_api_client.post(
        reverse("users:users-change-password"),
        {
            "current_password": "test",
            "new_password": "short",
            "new_password_confirm": "short",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_change_password_success_response_has_empty_body(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A successful change returns 204 with no body content."""
    user_fixture.set_password("test")
    user_fixture.save()

    response = authenticated_api_client.post(
        reverse("users:users-change-password"),
        {
            "current_password": "test",
            "new_password": "a-much-stronger-password-123",
            "new_password_confirm": "a-much-stronger-password-123",
        },
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""


@pytest.mark.django_db()
def test_change_password_does_not_affect_other_users(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
) -> None:
    """Changing the requesting user's password never touches another user's password."""
    user_fixture.set_password("test")
    user_fixture.save()
    admin_user_fixture.set_password("admin-password")
    admin_user_fixture.save()

    response = authenticated_api_client.post(
        reverse("users:users-change-password"),
        {
            "current_password": "test",
            "new_password": "a-much-stronger-password-123",
            "new_password_confirm": "a-much-stronger-password-123",
        },
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    admin_user_fixture.refresh_from_db()
    assert admin_user_fixture.check_password("admin-password") is True


@pytest.mark.django_db()
def test_change_password_allows_login_with_new_password_and_rejects_old(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    api_client: APIClient,
) -> None:
    """A successful change allows login with the new password and rejects the old one."""
    user_fixture.set_password("test")
    user_fixture.save()

    response = authenticated_api_client.post(
        reverse("users:users-change-password"),
        {
            "current_password": "test",
            "new_password": "a-much-stronger-password-123",
            "new_password_confirm": "a-much-stronger-password-123",
        },
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    old_password_response = api_client.post(
        reverse("token_obtain_pair"),
        {"email": user_fixture.email, "password": "test"},
    )
    assert old_password_response.status_code == status.HTTP_401_UNAUTHORIZED

    new_password_response = api_client.post(
        reverse("token_obtain_pair"),
        {"email": user_fixture.email, "password": "a-much-stronger-password-123"},
    )
    assert new_password_response.status_code == status.HTTP_200_OK
