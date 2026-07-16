"""Tests for the change-username action on UserViewSet."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.collections.models import Collection
from my_game_list.moderation.models import Report

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_change_username_unauthenticated(api_client: APIClient) -> None:
    """An unauthenticated request is rejected."""
    response = api_client.post(reverse("users:users-change-username"), {"username": "new_username"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_change_username_updates_username_and_slug(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A successful change updates both username and slug, returned in the response."""
    response = authenticated_api_client.post(
        reverse("users:users-change-username"),
        {"username": "new_username"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == "new_username"
    assert response.json()["slug"] == "new_username"

    user_fixture.refresh_from_db()
    assert user_fixture.username == "new_username"
    assert user_fixture.slug == "new_username"


@pytest.mark.django_db()
def test_change_username_rejects_same_as_current(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Submitting the current username as the 'new' one is rejected, not a silent no-op."""
    response = authenticated_api_client.post(
        reverse("users:users-change-username"),
        {"username": user_fixture.username},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_change_username_rejects_invalid_format(authenticated_api_client: APIClient) -> None:
    """A username violating the registration character rules is rejected."""
    response = authenticated_api_client.post(
        reverse("users:users-change-username"),
        {"username": "invalid username with spaces"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_change_username_rejects_username_taken_by_another_user(
    authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
) -> None:
    """A username already taken by another user is rejected."""
    response = authenticated_api_client.post(
        reverse("users:users-change-username"),
        {"username": admin_user_fixture.username},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_change_username_does_not_clear_moderation_flag(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """has_moderated_username stays set after a username change, per the 'never auto-clears' rule."""
    user_fixture.has_moderated_username = True
    user_fixture.save(update_fields=["has_moderated_username"])

    response = authenticated_api_client.post(
        reverse("users:users-change-username"),
        {"username": "new_username"},
    )

    assert response.status_code == status.HTTP_200_OK
    user_fixture.refresh_from_db()
    assert user_fixture.has_moderated_username is True


@pytest.mark.django_db()
def test_change_username_allowed_with_pending_report_against_it(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
) -> None:
    """A pending username Report doesn't block the user from changing it."""
    baker.make(
        Report,
        target_type=Report.TargetType.USERNAME,
        reported_by=admin_user_fixture,
        reported_user=user_fixture,
        reason="offensive username",
    )

    response = authenticated_api_client.post(
        reverse("users:users-change-username"),
        {"username": "new_username"},
    )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_change_username_cascades_to_owned_collection_slugs(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Changing username regenerates the slug of every collection the user owns."""
    collection = baker.make(Collection, user=user_fixture, name="My Favorites")
    assert collection.slug == "test_user-my-favorites"

    response = authenticated_api_client.post(
        reverse("users:users-change-username"),
        {"username": "new_username"},
    )

    assert response.status_code == status.HTTP_200_OK
    collection.refresh_from_db()
    assert collection.slug == "new_username-my-favorites"


@pytest.mark.django_db()
def test_change_username_slug_collision_gets_suffixed(
    authenticated_api_client: APIClient,
) -> None:
    """A new username that slugifies to an already-taken slug resolves with a numeric suffix."""
    User.objects.create(username="new_username_taker", email="taker@email.com", slug="new-username")

    response = authenticated_api_client.post(
        reverse("users:users-change-username"),
        {"username": "New-Username"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == "New-Username"
    assert response.json()["slug"] == "new-username-1"
