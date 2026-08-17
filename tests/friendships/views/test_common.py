"""Tests for common functionalities in the friendship application."""

from typing import TYPE_CHECKING, Any
from unittest.mock import ANY

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.parametrize(
    "viewname",
    [
        pytest.param(
            "friendships:friendships-list",
            id="Check the forbidden access to friendships.",
        ),
        pytest.param(
            "friendships:friendship-requests-list",
            id="Check the forbidden access to friendship requests.",
        ),
    ],
)
@pytest.mark.django_db()
def test_unauthorized_access_list(viewname: str, api_client: APIClient) -> None:
    """Check if the unauthorized user did not have access to the protected endpoints."""
    response = api_client.get(reverse(viewname))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Authentication credentials were not provided."}


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("post", id="PUT method"),
        pytest.param("put", id="PUT method"),
        pytest.param("patch", id="PATCH method"),
        pytest.param("delete", id="DELETE method"),
    ],
)
@pytest.mark.parametrize(
    "viewname",
    [
        pytest.param(
            "friendships:friendships-detail",
            id="Check unauthorized access for the friendships.",
        ),
        pytest.param(
            "friendships:friendship-requests-detail",
            id="Check unauthorized access for the friendship requests.",
        ),
    ],
)
@pytest.mark.django_db()
def test_unauthorized_access_detail(method: str, viewname: str, api_client: APIClient) -> None:
    """Check if the unauthorized user did not have access to the protected endpoints."""
    response = getattr(api_client, method)(reverse(viewname, (1,)))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Authentication credentials were not provided."}


@pytest.mark.parametrize(
    ("viewname", "fixture_name", "expected_result"),
    [
        pytest.param(
            "friendships:friendship-requests-list",
            "user_and_admin_friendship_request_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "created_at": "2023-06-23T08:21:12Z",
                        "last_modified_at": "2023-06-23T08:21:12Z",
                        "message": "",
                        "receiver": {
                            "id": ANY,
                            "gravatar_url": ANY,
                            "date_joined": "2023-05-25T14:21:13Z",
                            "email": None,
                            "last_active": None,
                            "is_active": True,
                            "last_login": None,
                            "is_staff": True,
                            "gender": ANY,
                            "slug": ANY,
                            "username": "test_admin",
                        },
                        "rejected_at": None,
                        "sender": {
                            "id": ANY,
                            "gravatar_url": ANY,
                            "date_joined": "2023-05-25T12:01:12Z",
                            "email": "test@email.com",
                            "last_active": None,
                            "is_active": True,
                            "last_login": None,
                            "is_staff": False,
                            "gender": ANY,
                            "slug": ANY,
                            "username": "test_user",
                        },
                    },
                ],
            },
            id="Test list endpoint for friendship requests.",
        ),
        pytest.param(
            "friendships:friendships-list",
            "user_and_admin_friendship_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "created_at": "2023-06-23T08:21:12Z",
                        "friend": {
                            "id": ANY,
                            "gravatar_url": ANY,
                            "date_joined": "2023-05-25T14:21:13Z",
                            "email": None,
                            "last_active": None,
                            "is_active": True,
                            "last_login": None,
                            "is_staff": True,
                            "gender": ANY,
                            "slug": ANY,
                            "username": "test_admin",
                        },
                        "user": {
                            "id": ANY,
                            "gravatar_url": ANY,
                            "date_joined": "2023-05-25T12:01:12Z",
                            "email": "test@email.com",
                            "last_active": None,
                            "is_active": True,
                            "last_login": None,
                            "is_staff": False,
                            "gender": ANY,
                            "slug": ANY,
                            "username": "test_user",
                        },
                    },
                ],
            },
            id="Test list endpoint for friendships.",
        ),
    ],
)
@pytest.mark.django_db()
def test_list_model(
    request: pytest.FixtureRequest,
    viewname: str,
    fixture_name: str,
    expected_result: dict[str, Any],
    authenticated_api_client: APIClient,
) -> None:
    """Test the list endpoint for the friendship models."""
    request.getfixturevalue(fixture_name)
    response = authenticated_api_client.get(reverse(viewname))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == expected_result


@pytest.mark.parametrize(
    ("viewname", "fixture_name", "expected_result"),
    [
        pytest.param(
            "friendships:friendship-requests-detail",
            "user_and_admin_friendship_request_fixture",
            {
                "id": ANY,
                "created_at": "2023-06-23T08:21:12Z",
                "last_modified_at": "2023-06-23T08:21:12Z",
                "message": "",
                "receiver": {
                    "id": ANY,
                    "gravatar_url": ANY,
                    "date_joined": "2023-05-25T14:21:13Z",
                    "email": None,
                    "last_active": None,
                    "is_active": True,
                    "last_login": None,
                    "gender": ANY,
                    "slug": ANY,
                    "username": "test_admin",
                    "is_staff": True,
                },
                "rejected_at": None,
                "sender": {
                    "id": ANY,
                    "gravatar_url": ANY,
                    "date_joined": "2023-05-25T12:01:12Z",
                    "email": "test@email.com",
                    "last_active": None,
                    "is_active": True,
                    "last_login": None,
                    "gender": ANY,
                    "slug": ANY,
                    "username": "test_user",
                    "is_staff": False,
                },
            },
            id="Get the friendship request by id.",
        ),
        pytest.param(
            "friendships:friendships-detail",
            "user_and_admin_friendship_fixture",
            {
                "id": ANY,
                "created_at": "2023-06-23T08:21:12Z",
                "friend": {
                    "id": ANY,
                    "gravatar_url": ANY,
                    "date_joined": "2023-05-25T14:21:13Z",
                    "email": None,
                    "last_active": None,
                    "is_active": True,
                    "last_login": None,
                    "gender": ANY,
                    "slug": ANY,
                    "username": "test_admin",
                    "is_staff": True,
                },
                "user": {
                    "id": ANY,
                    "gravatar_url": ANY,
                    "date_joined": "2023-05-25T12:01:12Z",
                    "email": "test@email.com",
                    "last_active": None,
                    "is_active": True,
                    "last_login": None,
                    "gender": ANY,
                    "slug": ANY,
                    "username": "test_user",
                    "is_staff": False,
                },
            },
            id="Get the friendship by id.",
        ),
    ],
)
@pytest.mark.django_db()
def test_get_model_detail(
    request: pytest.FixtureRequest,
    viewname: str,
    fixture_name: str,
    expected_result: dict[str, Any],
    authenticated_api_client: APIClient,
) -> None:
    """Check that the user can get the model instance data with the given id."""
    model_instance = request.getfixturevalue(fixture_name)
    response = authenticated_api_client.get(reverse(viewname, (model_instance.pk,)))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == expected_result


@pytest.mark.parametrize(
    ("viewname", "fixture_name"),
    [
        pytest.param(
            "friendships:friendship-requests-detail",
            "user_and_admin_friendship_request_fixture",
            id="Delete the friendship request.",
        ),
        pytest.param(
            "friendships:friendships-detail",
            "user_and_admin_friendship_fixture",
            id="Delete the friendship.",
        ),
    ],
)
@pytest.mark.django_db()
def test_delete_model(
    request: pytest.FixtureRequest,
    viewname: str,
    fixture_name: str,
    admin_authenticated_api_client: APIClient,
) -> None:
    """Check if deletion of the game model works properly."""
    model_instance = request.getfixturevalue(fixture_name)
    response = admin_authenticated_api_client.delete(reverse(viewname, (model_instance.pk,)))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert model_instance.__class__.objects.count() == 0
