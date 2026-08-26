"""Tests for the Collection API 'items' field limit in list view."""

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import Collection
    from game_list.games.models import Game
    from game_list.users.models import User


@pytest.mark.django_db()
def test_collection_list_items_field_limit(authenticated_api_client: APIClient, user_fixture: User) -> None:
    """Test that the collection list view returns a maximum of 5 items per collection."""
    # Create a collection
    collection: Collection = baker.make("collections.Collection", user=user_fixture, visibility="PUB")

    # Create 7 games with specific cover image IDs
    games: list[Game] = [baker.make("games.Game", cover_image_id=f"img_{i}") for i in range(7)]

    # Add games to collection with specific order
    for i, game in enumerate(games):
        baker.make("collections.CollectionItem", collection=collection, game=game, order=i + 1, added_by=user_fixture)

    # Get the list of collections
    url = reverse("collections:collections-list")
    response = authenticated_api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    results = response.data.get("results", response.data)
    assert len(results) == 1

    collection_data = results[0]
    assert "items_cover_image_ids" in collection_data
    items = collection_data["items_cover_image_ids"]

    # Check limit (should be 5, not 7)
    items_limit = 5
    assert len(items) == items_limit

    # Check content (should be image IDs)
    expected_ids = [f"img_{i}" for i in range(items_limit)]
    assert items == expected_ids


@pytest.mark.django_db()
def test_collection_detail_items_field(authenticated_api_client: APIClient, user_fixture: User) -> None:
    """Test that the collection detail view returns the full list of item objects."""
    # Ensure detail view still returns full items list (via CollectionItemSerializer)
    # The detail serializer overrides 'items', so it should return objects, not IDs.

    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    game: Game = baker.make("games.Game", cover_image_id="img_detail")
    baker.make("collections.CollectionItem", collection=collection, game=game, order=1)

    url = reverse("collections:collections-detail", kwargs={"pk": collection.pk})
    response = authenticated_api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.data

    assert "items" in data
    items = data["items"]
    assert len(items) == 1
    # Detail view returns full objects
    assert isinstance(items[0], dict)
    assert items[0]["game"]["cover_image_id"] == "img_detail"
