"""Tests for user app views."""

from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.parametrize(
    ("viewname", "args"),
    [
        pytest.param(
            "users:users-list",
            (),
            id="Check unauthorized access for getting a list of users.",
        ),
        pytest.param(
            "users:users-detail",
            (1,),
            id="Check unauthorized access for getting a user with given id.",
        ),
    ],
)
@pytest.mark.django_db()
def test_unauthorized_access(viewname: str, args: Sequence[int], api_client: APIClient) -> None:
    """Check if the unauthorized user did not have access to the protected endpoints."""
    response = api_client.get(reverse(viewname, args))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Authentication credentials were not provided."}


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
                "email": "test_admin@email.com",
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
            "total": 0,
        },
    }


@pytest.mark.django_db()
def test_register_user(api_client: APIClient) -> None:
    """Check if registration process is successful."""
    data = {
        "username": "testuser",
        "password": "testpassword",
        "email": "test@test.com",
    }
    response = api_client.post(reverse("users:users-list"), data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["username"] == "testuser"
