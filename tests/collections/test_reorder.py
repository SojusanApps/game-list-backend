"""Tests for the Collection reorder items endpoint."""

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
class TestCollectionReorderItems:
    """Tests for the reorder-items action in CollectionViewSet."""

    def test_reorder_items_success(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test successfully reordering items in a collection."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)
        item3: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=3)

        # Move item3 to position 0 (beginning)
        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": item3.pk},
        )
        data = {"position": 0}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "order" in response.data

        item3.refresh_from_db()
        item1.refresh_from_db()
        # item3's new order should be less than item1's order (it's now first)
        assert item3.order is not None
        assert item1.order is not None
        assert item3.order < item1.order

    def test_reorder_items_not_owner(
        self,
        authenticated_api_client: APIClient,
    ) -> None:
        """Test that a non-owner cannot reorder items in a private collection."""
        other_user: User = baker.make("users.User")
        collection: Collection = baker.make("collections.Collection", user=other_user, visibility="PRI")
        item: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)

        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": item.pk},
        )
        data = {"position": 0}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND  # Because get_queryset filters it out

    def test_reorder_items_invalid_id(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test reordering with an item ID that doesn't belong to the collection."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        other_collection: Collection = baker.make("collections.Collection", user=user_fixture)
        other_item: CollectionItem = baker.make("collections.CollectionItem", collection=other_collection)

        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": other_item.pk},
        )
        data = {"position": 0}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found in this collection" in response.data["detail"]

    def test_reorder_items_collaborative(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that a collaborator can reorder items in a collaborative collection."""
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

        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": item2.pk},
        )
        data = {"position": 0}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "order" in response.data
        item2.refresh_from_db()
        item1.refresh_from_db()
        # item2 should now be before item1
        assert item2.order is not None
        assert item1.order is not None
        assert item2.order < item1.order

    def test_reorder_item_to_middle_position(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test reordering an item to the middle of a collection."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)
        item2: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=2)
        item3: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=3)

        # Move item1 to position 1 (between item2 and item3 in the list without item1)
        # After excluding item1, the list is: [item2 at pos 0, item3 at pos 1]
        # Position 1 means "between pos 0 and pos 1", i.e., between item2 and item3
        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": item1.pk},
        )
        data = {"position": 1}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        item1.refresh_from_db()
        item2.refresh_from_db()
        item3.refresh_from_db()
        # item1 should now be between item2 and item3
        assert item1.order is not None
        assert item2.order is not None
        assert item3.order is not None
        assert item2.order < item1.order < item3.order

    def test_reorder_item_to_end(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test reordering an item to the end of a collection."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item1: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)
        item3: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=3)

        # Move item1 to the end (position 3 or higher)
        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": item1.pk},
        )
        data = {"position": 10}  # Position beyond the end

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        item1.refresh_from_db()
        item3.refresh_from_db()
        # item1 should now be after item3
        assert item1.order is not None
        assert item3.order is not None
        assert item1.order > item3.order

    def test_reorder_only_item_to_position_zero(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that reordering the only item in a collection to position 0 defaults to order 1.0."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=5)

        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": item.pk},
        )
        data = {"position": 0}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.order == Decimal("1.0")

    def test_reorder_only_item_to_position_beyond_end(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that reordering the only item in a collection past the end defaults to order 1.0."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        item: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=5)

        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": item.pk},
        )
        data = {"position": 10}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.order == Decimal("1.0")

    def test_reorder_item_between_items_with_equal_order_appends_to_end(
        self,
        authenticated_api_client: APIClient,
        user_fixture: User,
    ) -> None:
        """Test that reordering between two items sharing the same order appends after the last one instead."""
        collection: Collection = baker.make("collections.Collection", user=user_fixture)
        moving_item: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=1)
        tied_item_a: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=5)
        tied_item_b: CollectionItem = baker.make("collections.CollectionItem", collection=collection, order=5)

        url = reverse(
            "collections:collections-reorder-item",
            kwargs={"pk": collection.pk, "item_id": moving_item.pk},
        )
        data = {"position": 1}

        response = authenticated_api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        moving_item.refresh_from_db()
        tied_item_a.refresh_from_db()
        tied_item_b.refresh_from_db()
        # Falls back to appending after the last tied item instead of computing a duplicate midpoint
        assert tied_item_a.order == Decimal(5)
        assert tied_item_b.order == Decimal(5)
        assert moving_item.order == Decimal("6.0")
