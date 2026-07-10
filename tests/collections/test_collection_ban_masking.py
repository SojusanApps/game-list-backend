"""Wiring check: a banned user's collections are masked for others even if never individually reported."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.collections.models import Collection
from my_game_list.moderation.masking import MODERATION_PLACEHOLDER_TEXT

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_banned_users_unreported_collection_is_masked_for_stranger_but_not_owner(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A never-individually-reported collection from a banned user is masked for strangers, visible to its owner."""
    collection = Collection.objects.create(
        name="a fine name",
        description="a fine description",
        user=user_fixture,
        visibility="PUB",
    )
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("collections:collections-detail", kwargs={"pk": collection.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["name"] == MODERATION_PLACEHOLDER_TEXT
    assert stranger_response.data["description"] == MODERATION_PLACEHOLDER_TEXT

    api_client.force_authenticate(user=user_fixture)
    owner_response = api_client.get(reverse("collections:collections-detail", kwargs={"pk": collection.id}))
    assert owner_response.status_code == status.HTTP_200_OK
    assert owner_response.data["name"] == collection.name
    assert owner_response.data["description"] == collection.description


@pytest.mark.django_db()
def test_banned_user_can_still_create_a_collection(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A banned user can still successfully create a new Collection - no write-time restriction."""
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])
    api_client.force_authenticate(user=user_fixture)

    response = api_client.post(
        reverse("collections:collections-list"),
        {"name": "a collection from a banned user", "description": "a note"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
