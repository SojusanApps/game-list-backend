"""Tests for the Collection update tiers endpoint."""

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from game_list.collections.models import Tier

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import Collection, CollectionItem
    from game_list.users.models import User


@pytest.mark.django_db()
class TestCollectionUpdateTiers:
    """Tests for the update-tiers action in CollectionViewSet."""

    def test_update_tiers_success(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test successfully updating tier for a single item in a collection."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, tier=Tier.A)

        url = reverse(
            "collections:collections-update-tier",
            kwargs={"pk": collection.pk, "item_id": item1.pk},
        )
        data = {"tier": Tier.S}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "order" in response.data

        item1.refresh_from_db()
        assert item1.tier == Tier.S

    def test_update_tiers_not_owner(
        self,
        authenticated_api_client: APIClient,
    ) -> None:
        """Test that a non-owner cannot update tiers in a private collection."""
        other_user: User = baker.make("users.User")
        collection: Collection = baker.make("collections.Collection", user=other_user, visibility="PRI")
        item: CollectionItem = baker.make("collections.CollectionItem", collection=collection, tier=Tier.B)

        url = reverse(
            "collections:collections-update-tier",
            kwargs={"pk": collection.pk, "item_id": item.pk},
        )
        data = {"tier": Tier.S}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_tiers_invalid_id(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test updating tiers with an item ID that doesn't belong to the collection."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        other_collection: Collection = baker.make("collections.Collection", user=user_fixture)
        other_item: CollectionItem = baker.make("collections.CollectionItem", collection=other_collection)

        url = reverse(
            "collections:collections-update-tier",
            kwargs={"pk": collection.pk, "item_id": other_item.pk},
        )
        data = {"tier": Tier.S}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found in this collection" in response.data["detail"]

    def test_update_tiers_collaborative(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that a collaborator can update tiers in a collaborative collection."""
        owner: User = baker.make("users.User")
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            mode="C",  # COLLABORATIVE
            visibility="PUB",
        )
        collection.collaborators.add(user_fixture)
        item: CollectionItem = baker.make("collections.CollectionItem", collection=collection, tier=Tier.B)

        url = reverse(
            "collections:collections-update-tier",
            kwargs={"pk": collection.pk, "item_id": item.pk},
        )
        data = {"tier": Tier.S}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.tier == Tier.S

    def test_update_tier_with_position(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test successfully updating tier with a specific position."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make(
            "collections.CollectionItem",
            collection=collection,
            tier=Tier.S,
            order=1,
        )
        item2: CollectionItem = baker.make(
            "collections.CollectionItem",
            collection=collection,
            tier=Tier.B,
            order=1,
        )

        # Move item2 to tier S at position 0 (before item1)
        url = reverse(
            "collections:collections-update-tier",
            kwargs={"pk": collection.pk, "item_id": item2.pk},
        )
        data = {"tier": Tier.S, "position": 0}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "order" in response.data

        item1.refresh_from_db()
        item2.refresh_from_db()
        assert item2.tier == Tier.S
        # item2 should now be before item1 in tier S
        assert item2.order is not None
        assert item1.order is not None
        assert item2.order < item1.order
