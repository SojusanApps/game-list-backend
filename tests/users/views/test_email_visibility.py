"""Wiring check: UserSerializer/UserDetailSerializer.email is visible only to the owner and staff."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_email_is_hidden_from_a_stranger_on_detail(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A non-owner, non-staff viewer sees email: null on GET /users/{id}/."""
    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)

    response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] is None


@pytest.mark.django_db()
def test_email_is_hidden_from_a_stranger_on_list(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A non-owner, non-staff viewer sees email: null for another user on GET /users/."""
    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    [entry] = [row for row in response.data["results"] if row["id"] == user_fixture.id]
    assert entry["email"] is None


@pytest.mark.django_db()
def test_email_is_visible_to_self_and_staff(
    api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
) -> None:
    """The owner sees their own email; staff sees anyone's, on both list and detail."""
    api_client.force_authenticate(user=user_fixture)
    self_detail = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert self_detail.data["email"] == user_fixture.email

    api_client.force_authenticate(user=admin_user_fixture)
    staff_detail = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert staff_detail.data["email"] == user_fixture.email

    staff_list = api_client.get(reverse("users:users-list"))
    [entry] = [row for row in staff_list.data["results"] if row["id"] == user_fixture.id]
    assert entry["email"] == user_fixture.email
