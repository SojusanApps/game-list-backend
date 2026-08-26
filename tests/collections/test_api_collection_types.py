"""Tests for collection types API."""

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from game_list.collections.models import CollectionType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import Collection
    from game_list.games.models import Game
    from game_list.users.models import User


@pytest.mark.django_db()
class TestCollectionTypeAPI:
    """Tests for collection type API functionality."""

    def test_filter_collections_by_type(self, api_client: APIClient, user_fixture: User) -> None:
        """Test filtering collections by type."""
        api_client.force_authenticate(user=user_fixture)

        baker.make("collections.Collection", user=user_fixture, type=CollectionType.NORMAL, _quantity=2)
        baker.make("collections.Collection", user=user_fixture, type=CollectionType.RANK, _quantity=1)
        baker.make("collections.Collection", user=user_fixture, type=CollectionType.TIER, _quantity=1)

        url = reverse("collections:collections-list")

        # Filter for RANK
        response = api_client.get(url, {"type": CollectionType.RANK})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["type"] == CollectionType.RANK

        # Filter for NORMAL
        expected_normal_count = 2
        response = api_client.get(url, {"type": CollectionType.NORMAL})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == expected_normal_count

    def test_create_collection_item_no_validation_required(self, api_client: APIClient, user_fixture: User) -> None:
        """Test that API allows creating collection items without order/tier even for special types."""
        api_client.force_authenticate(user=user_fixture)

        rank_collection: Collection = baker.make(
            "collections.Collection",
            user=user_fixture,
            type=CollectionType.RANK,
        )
        game: Game = baker.make("games.Game")

        url = reverse("collections:collection-items-list")

        # Create item for RANK collection without order
        data = {
            "collection": rank_collection.id,
            "game": game.id,
            "order": None,
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        # Create item for TIER collection without tier
        tier_collection: Collection = baker.make(
            "collections.Collection",
            user=user_fixture,
            type=CollectionType.TIER,
        )
        tier_data = {
            "collection": tier_collection.id,
            "game": game.id,
            "tier": "",
        }
        response = api_client.post(url, tier_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
