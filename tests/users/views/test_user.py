"""Tests for user app views."""

from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import Game, GameList, GameListStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_list_users_as_anonymous(api_client: APIClient, user_fixture: UserModel) -> None:
    """An anonymous caller can list active user accounts, same as a non-staff caller."""
    baker.make(User, username="inactive_user", email="inactive@email.com", is_active=False)

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {result["id"] for result in response.json()["results"]}
    assert returned_ids == {user_fixture.pk}


@pytest.mark.django_db()
def test_get_user_as_anonymous(api_client: APIClient, user_fixture: UserModel) -> None:
    """An anonymous caller can retrieve an active user account by ID, with private fields masked."""
    response = api_client.get(reverse("users:users-detail", (user_fixture.pk,)))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["id"] == user_fixture.pk
    assert body["email"] is None


@pytest.mark.django_db()
def test_get_inactive_user_not_found_for_anonymous(api_client: APIClient) -> None:
    """An anonymous caller gets a 404 when retrieving an inactive account by ID."""
    inactive_user = baker.make(User, username="inactive_user", email="inactive@email.com", is_active=False)

    response = api_client.get(reverse("users:users-detail", (inactive_user.pk,)))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db()
def test_list_users(authenticated_api_client: APIClient, admin_user_fixture: UserModel) -> None:  # noqa: ARG001
    """Check that authorized user can access the list of users."""
    response = authenticated_api_client.get(reverse("users:users-list"))
    users_ids = User.objects.all().values_list("id", flat=True)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": users_ids[0],
                "slug": ANY,
                "username": "test_user",
                "email": "test@email.com",
                "gender": "",
                "last_active": None,
                "last_login": None,
                "date_joined": "2023-05-25T12:01:12Z",
                "gravatar_url": ANY,
                "is_active": True,
                "is_staff": False,
            },
            {
                "id": users_ids[1],
                "slug": ANY,
                "username": "test_admin",
                "email": None,
                "gender": "",
                "last_active": None,
                "last_login": None,
                "date_joined": "2023-05-25T14:21:13Z",
                "gravatar_url": ANY,
                "is_active": True,
                "is_staff": True,
            },
        ],
    }


@pytest.mark.django_db()
def test_list_users_excludes_inactive_for_non_staff(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A non-staff caller does not see inactive accounts in the list."""
    baker.make(User, username="inactive_user", email="inactive@email.com", is_active=False)

    response = authenticated_api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {result["id"] for result in response.json()["results"]}
    assert returned_ids == {user_fixture.pk}


@pytest.mark.django_db()
def test_list_users_includes_inactive_for_staff(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
) -> None:
    """A staff caller sees inactive accounts in the list."""
    inactive_user = baker.make(User, username="inactive_user", email="inactive@email.com", is_active=False)

    response = admin_authenticated_api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {result["id"] for result in response.json()["results"]}
    assert returned_ids == {admin_user_fixture.pk, inactive_user.pk}


@pytest.mark.django_db()
def test_get_inactive_user_not_found_for_non_staff(authenticated_api_client: APIClient) -> None:
    """A non-staff caller gets a 404 when retrieving an inactive account by ID."""
    inactive_user = baker.make(User, username="inactive_user", email="inactive@email.com", is_active=False)

    response = authenticated_api_client.get(reverse("users:users-detail", (inactive_user.pk,)))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db()
def test_get_inactive_user_found_for_staff(admin_authenticated_api_client: APIClient) -> None:
    """A staff caller can retrieve an inactive account by ID."""
    inactive_user = baker.make(User, username="inactive_user", email="inactive@email.com", is_active=False)

    response = admin_authenticated_api_client.get(reverse("users:users-detail", (inactive_user.pk,)))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == inactive_user.pk


@pytest.mark.django_db()
def test_get_user(authenticated_api_client: APIClient) -> None:
    """Check that authorized user can get the user with the given id."""
    user = User.objects.all().first()
    if not user:
        raise User.DoesNotExist
    response = authenticated_api_client.get(reverse("users:users-detail", (user.pk,)))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": user.pk,
        "slug": ANY,
        "email": "test@email.com",
        "username": "test_user",
        "gender": "",
        "last_active": None,
        "last_login": None,
        "date_joined": "2023-05-25T12:01:12Z",
        "gravatar_url": ANY,
        "friends": [],
        "latest_game_list_updates": [],
        "is_staff": False,
        "warning_count": 0,
        "game_list_statistics": {
            "completed": 0,
            "dropped": 0,
            "mean_score": None,
            "on_hold": 0,
            "plan_to_play": 0,
            "playing": 0,
            "not_planned": 0,
            "total": 0,
        },
    }


@pytest.mark.django_db()
def test_get_user_game_list_statistics_counts_not_planned(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """The not_planned status is counted in its own breakdown key, separate from the other statuses."""
    baker.make(GameList, user=user_fixture, game=baker.make(Game), status=GameListStatus.NOT_PLANNED, score=None)
    baker.make(GameList, user=user_fixture, game=baker.make(Game), status=GameListStatus.NOT_PLANNED, score=None)
    baker.make(GameList, user=user_fixture, game=baker.make(Game), status=GameListStatus.COMPLETED, score=8)

    response = authenticated_api_client.get(reverse("users:users-detail", (user_fixture.pk,)))

    assert response.status_code == status.HTTP_200_OK
    statistics = response.json()["game_list_statistics"]
    assert statistics["not_planned"] == 2  # noqa: PLR2004
    assert statistics["completed"] == 1
    assert statistics["total"] == 3  # noqa: PLR2004


@pytest.mark.django_db()
def test_self_registration_is_removed(authenticated_api_client: APIClient) -> None:
    """Self-registration is gone now that Keycloak is the sole account-provisioning path (ADR-0010)."""
    data = {
        "username": "testuser",
        "password": "testpassword",
        "email": "test@test.com",
    }
    response = authenticated_api_client.post(reverse("users:users-list"), data)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert not User.objects.filter(username="testuser").exists()


@pytest.mark.django_db()
def test_self_registration_is_removed_for_unauthenticated_caller(api_client: APIClient) -> None:
    """An unauthenticated POST is rejected the same way as an authenticated one: no create action exists."""
    response = api_client.post(reverse("users:users-list"), {})

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert not User.objects.filter(username="testuser").exists()
