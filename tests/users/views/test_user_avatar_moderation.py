"""Wiring check: UserSerializer/UserSimpleSerializer/UserDetailSerializer.gravatar_url goes through masking."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_moderated_avatar_is_empty_for_literally_every_viewer_including_self_and_staff(
    api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
) -> None:
    """has_moderated_avatar hides gravatar_url from everyone: strangers, the flagged user, and staff."""
    user_fixture.has_moderated_avatar = True
    user_fixture.save(update_fields=["has_moderated_avatar"])
    assert user_fixture.gravatar_url != ""

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["gravatar_url"] == ""

    api_client.force_authenticate(user=user_fixture)
    self_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert self_response.status_code == status.HTTP_200_OK
    assert self_response.data["gravatar_url"] == ""

    api_client.force_authenticate(user=admin_user_fixture)
    staff_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert staff_response.status_code == status.HTTP_200_OK
    assert staff_response.data["gravatar_url"] == ""


@pytest.mark.django_db()
def test_banned_without_moderated_avatar_hides_avatar_from_others_but_not_self(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """is_banned alone (no has_moderated_avatar) hides gravatar_url from others, but the user still sees their own."""
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])
    real_gravatar_url = user_fixture.gravatar_url

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["gravatar_url"] == ""

    api_client.force_authenticate(user=user_fixture)
    self_response = api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))
    assert self_response.status_code == status.HTTP_200_OK
    assert self_response.data["gravatar_url"] == real_gravatar_url
