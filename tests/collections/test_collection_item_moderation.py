"""Wiring check: CollectionItemSerializer.description goes through the shared moderation masking helper."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.collections.models import Collection, CollectionItem
from my_game_list.moderation.masking import MODERATION_PLACEHOLDER_TEXT

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import Game
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_moderated_collection_item_note_shows_placeholder_to_stranger_and_real_text_to_added_by(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A CollectionItem flagged is_moderated masks description for a stranger, real text for added_by."""
    collection = Collection.objects.create(name="a public collection", user=user_fixture, visibility="PUB")
    game: Game = baker.make("games.Game")
    item = CollectionItem.objects.create(
        collection=collection,
        game=game,
        added_by=user_fixture,
        description="a bad note",
        is_moderated=True,
    )

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("collections:collection-items-detail", kwargs={"pk": item.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["description"] == MODERATION_PLACEHOLDER_TEXT

    api_client.force_authenticate(user=user_fixture)
    owner_response = api_client.get(reverse("collections:collection-items-detail", kwargs={"pk": item.id}))
    assert owner_response.status_code == status.HTTP_200_OK
    assert owner_response.data["description"] == item.description


@pytest.mark.django_db()
def test_collection_item_note_with_null_added_by_is_masked_for_everyone_when_moderated(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A moderated item whose adding user was deleted (added_by null) is masked for every viewer, no crash."""
    collection = Collection.objects.create(name="a public collection", user=user_fixture, visibility="PUB")
    game: Game = baker.make("games.Game")
    item = CollectionItem.objects.create(
        collection=collection,
        game=game,
        added_by=None,
        description="a bad note",
        is_moderated=True,
    )

    api_client.force_authenticate(user=user_fixture)
    response = api_client.get(reverse("collections:collection-items-detail", kwargs={"pk": item.id}))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["description"] == MODERATION_PLACEHOLDER_TEXT
