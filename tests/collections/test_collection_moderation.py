"""Wiring check: CollectionSerializer.name/description go through the shared moderation masking helper."""

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
def test_moderated_collection_shows_placeholder_for_name_and_description_to_stranger_not_owner(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A collection flagged is_moderated masks both name and description for a stranger, real for the owner."""
    collection = Collection.objects.create(
        name="a bad name",
        description="a bad description",
        user=user_fixture,
        is_moderated=True,
        visibility="PUB",
    )

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
