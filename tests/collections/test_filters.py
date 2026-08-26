"""Tests for collection and collection item filters."""

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from game_list.collections.filters import CollectionItemFilterSet
from game_list.collections.models import CollectionItem

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import Collection
    from game_list.users.models import User


@pytest.mark.django_db()
def test_member_filter_returns_owned_and_collaborated_collections(
    api_client: APIClient,
    user_fixture: User,
) -> None:
    """Test that the member filter matches collections the user owns or collaborates on."""
    other_user: User = baker.make("users.User")
    owned: Collection = baker.make("collections.Collection", user=user_fixture)
    collaborated: Collection = baker.make("collections.Collection", user=other_user)
    collaborated.collaborators.add(user_fixture)
    unrelated: Collection = baker.make("collections.Collection", user=other_user)

    api_client.force_authenticate(user_fixture)
    url = reverse("collections:collections-list")
    response = api_client.get(url, {"member": user_fixture.id})

    assert response.status_code == status.HTTP_200_OK
    collection_ids = {c["id"] for c in response.data["results"]}
    assert collection_ids == {owned.id, collaborated.id}
    assert unrelated.id not in collection_ids


@pytest.mark.django_db()
def test_has_tier_true_returns_only_items_with_a_tier(
    api_client: APIClient,
    user_fixture: User,
) -> None:
    """Test that has_tier=true returns only items that have a tier assigned."""
    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    with_tier: CollectionItem = baker.make("collections.CollectionItem", collection=collection, tier="S")
    baker.make("collections.CollectionItem", collection=collection, tier="")

    api_client.force_authenticate(user_fixture)
    url = reverse("collections:collection-items-list")
    response = api_client.get(url, {"has_tier": "true"})

    assert response.status_code == status.HTTP_200_OK
    item_ids = {i["id"] for i in response.data["results"]}
    assert item_ids == {with_tier.id}


@pytest.mark.django_db()
def test_has_tier_false_returns_only_items_without_a_tier(
    api_client: APIClient,
    user_fixture: User,
) -> None:
    """Test that has_tier=false returns only items that have no tier assigned."""
    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    baker.make("collections.CollectionItem", collection=collection, tier="S")
    without_tier: CollectionItem = baker.make("collections.CollectionItem", collection=collection, tier="")

    api_client.force_authenticate(user_fixture)
    url = reverse("collections:collection-items-list")
    response = api_client.get(url, {"has_tier": "false"})

    assert response.status_code == status.HTTP_200_OK
    item_ids = {i["id"] for i in response.data["results"]}
    assert item_ids == {without_tier.id}


@pytest.mark.django_db()
def test_filter_has_tier_returns_queryset_unchanged_for_a_non_boolean_value() -> None:
    """Test the defensive fallback that returns the queryset unchanged for a non-boolean value.

    This branch is unreachable through the API: django-filter's FilterMethod wrapper
    short-circuits on empty values (None, "", etc.) before ever calling the filter method,
    and a BooleanFilter's cleaned value can only ever be True, False, or one of those empty
    values. The method is called directly here to exercise the fallback for coverage.
    """
    queryset = CollectionItem.objects.all()
    result = CollectionItemFilterSet().filter_has_tier(queryset, "has_tier", None)  # type: ignore[arg-type]
    assert result is queryset
