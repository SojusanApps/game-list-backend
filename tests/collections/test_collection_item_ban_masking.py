"""Wiring check: a banned added_by's item notes are masked for others even if never individually reported."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.collections.models import Collection, CollectionItem, CollectionMode
from my_game_list.moderation.masking import MODERATION_PLACEHOLDER_TEXT

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import Game
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_banned_added_bys_unreported_item_note_is_masked_for_stranger_but_not_added_by(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A never-individually-reported note from a banned added_by is masked for strangers, visible to added_by."""
    collection = Collection.objects.create(name="a public collection", user=user_fixture, visibility="PUB")
    game: Game = baker.make("games.Game")
    item = CollectionItem.objects.create(
        collection=collection,
        game=game,
        added_by=user_fixture,
        description="a fine note",
    )
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])

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
def test_banned_collaborator_can_still_add_a_collection_item(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A banned user can still add a CollectionItem as a collaborator - no write-time restriction."""
    collection_owner: UserModel = user_fixture.__class__.objects.create(
        username="collection_owner",
        email="collection_owner@email.com",
    )
    collection = Collection.objects.create(
        name="a collaborative collection",
        user=collection_owner,
        mode=CollectionMode.COLLABORATIVE,
    )
    collection.collaborators.add(user_fixture)
    game: Game = baker.make("games.Game")

    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])
    api_client.force_authenticate(user=user_fixture)

    response = api_client.post(
        reverse("collections:collection-items-list"),
        {"collection": collection.id, "game": game.id, "description": "added by a banned collaborator"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
