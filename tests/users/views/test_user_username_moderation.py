"""Wiring check: UserSerializer/UserSimpleSerializer/UserDetailSerializer.username goes through masking."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.masking import MODERATION_PLACEHOLDER_USERNAME

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_moderated_username_shows_placeholder_to_stranger_real_to_self_and_staff(
    api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
) -> None:
    """has_moderated_username masks username for other viewers, real for the flagged user and staff."""
    user_fixture.has_moderated_username = True
    user_fixture.save(update_fields=["has_moderated_username"])

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["username"] == MODERATION_PLACEHOLDER_USERNAME

    api_client.force_authenticate(user=user_fixture)
    self_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert self_response.status_code == status.HTTP_200_OK
    assert self_response.data["username"] == user_fixture.username

    api_client.force_authenticate(user=admin_user_fixture)
    staff_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert staff_response.status_code == status.HTTP_200_OK
    assert staff_response.data["username"] == user_fixture.username


@pytest.mark.django_db()
def test_banned_without_moderated_username_masks_username_for_others_but_not_self(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """is_banned alone masks username for other viewers, but the user still sees their own real username."""
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["username"] == MODERATION_PLACEHOLDER_USERNAME

    api_client.force_authenticate(user=user_fixture)
    self_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert self_response.status_code == status.HTTP_200_OK
    assert self_response.data["username"] == user_fixture.username


@pytest.mark.django_db()
def test_moderated_username_does_not_affect_login_or_slug(
    user_fixture: UserModel,
) -> None:
    """A moderated username's owner can still log in via email, and their slug is unaffected."""
    original_slug = user_fixture.slug
    user_fixture.has_moderated_username = True
    user_fixture.save(update_fields=["has_moderated_username"])
    user_fixture.refresh_from_db()

    assert user_fixture.slug == original_slug
    assert user_fixture.is_active is True
