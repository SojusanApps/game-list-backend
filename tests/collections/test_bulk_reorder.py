"""Tests for the Collection bulk-reorder endpoint."""

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import Collection, CollectionItem
    from game_list.users.models import User


@pytest.mark.django_db()
class TestCollectionBulkReorder:
    """Tests for the bulk_reorder action in CollectionViewSet."""

    def _url(self, collection_pk: int) -> str:
        return reverse("collections:collections-bulk-reorder", kwargs={"pk": collection_pk})

    def test_bulk_reorder_success(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test successfully bulk-reordering all items in a collection."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)
        item2: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=2)
        item3: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=3)

        # Reverse the order so item3 → pos 0, item2 → pos 1, item1 → pos 2
        data = {
            "items": [
                {"id": item3.pk, "position": 0},
                {"id": item2.pk, "position": 1},
                {"id": item1.pk, "position": 2},
            ],
        }

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        item1.refresh_from_db()
        item2.refresh_from_db()
        item3.refresh_from_db()

        # Orders are reset to the provided positions
        assert item3.order == Decimal(0)
        assert item2.order == Decimal(1)
        assert item1.order == Decimal(2)

    def test_bulk_reorder_resets_fractional_ordering(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that bulk reorder resets fractional order values to integers."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        # Items with fractional order values from previous fractional operations
        item1: CollectionItem = baker.make(
            "collections.CollectionItem",
            collection=collection,
            order=Decimal("1.5"),
        )
        item2: CollectionItem = baker.make(
            "collections.CollectionItem",
            collection=collection,
            order=Decimal("3.75"),
        )

        data = {
            "items": [
                {"id": item1.pk, "position": 0},
                {"id": item2.pk, "position": 1},
            ],
        }

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        item1.refresh_from_db()
        item2.refresh_from_db()

        assert item1.order == Decimal(0)
        assert item2.order == Decimal(1)

    def test_bulk_reorder_missing_items_returns_400(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that omitting items from the payload returns HTTP 400."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)
        baker.make("collections.CollectionItem", collection=collection, order=2)  # item2 not referenced

        data = {
            "items": [
                {"id": item1.pk, "position": 0},
            ],
        }

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_reorder_item_not_in_collection_returns_404(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that referencing an item from another collection returns HTTP 404."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)

        other_collection: Collection = baker.make("collections.Collection", user=user_fixture)
        other_item: CollectionItem = baker.make(
            "collections.CollectionItem",
            collection=other_collection,
            order=1,
        )

        data = {
            "items": [
                {"id": item1.pk, "position": 0},
                {"id": other_item.pk, "position": 1},
            ],
        }

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_bulk_reorder_duplicate_ids_returns_400(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that duplicate item IDs in the payload are rejected."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)

        data = {
            "items": [
                {"id": item1.pk, "position": 0},
                {"id": item1.pk, "position": 1},
            ],
        }

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_reorder_duplicate_positions_returns_400(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that duplicate positions in the payload are rejected."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)
        item2: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=2)

        data = {
            "items": [
                {"id": item1.pk, "position": 0},
                {"id": item2.pk, "position": 0},  # same position
            ],
        }

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_reorder_not_owner_returns_403_or_404(
        self,
        authenticated_api_client: APIClient,
    ) -> None:
        """Test that a non-owner cannot bulk-reorder a private collection."""
        other_user: User = baker.make("users.User")
        collection: Collection = baker.make(
            "collections.Collection",
            user=other_user,
            visibility="PRI",
        )
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)

        data = {
            "items": [
                {"id": item1.pk, "position": 0},
            ],
        }

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        # Private collection is not in queryset → 404
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_bulk_reorder_collaborator_can_reorder(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that a collaborator can bulk-reorder items in a collaborative collection."""
        owner: User = baker.make("users.User")
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            mode="C",  # COLLABORATIVE
            visibility="PUB",
        )
        collection.collaborators.add(user_fixture)

        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)
        item2: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=2)

        data = {
            "items": [
                {"id": item2.pk, "position": 0},
                {"id": item1.pk, "position": 1},
            ],
        }

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        item1.refresh_from_db()
        item2.refresh_from_db()
        assert item2.order == Decimal(0)
        assert item1.order == Decimal(1)

    def test_bulk_reorder_empty_collection(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that an empty payload is accepted for a collection with no items."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)

        data: dict[str, list[dict[str, int]]] = {"items": []}

        response = authenticated_api_client.post(self._url(collection.pk), data, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT
