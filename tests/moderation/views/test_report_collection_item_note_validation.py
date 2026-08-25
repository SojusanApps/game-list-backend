"""Test ReportViewSet.create validation for CollectionItem targets, including the null added_by edge case."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.collections.models import Collection, CollectionItem, CollectionMode
from game_list.moderation.models import ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_rejects_report_against_collection_item_with_null_added_by(
    authenticated_api_client: APIClient,
    other_user_collection_item_fixture: CollectionItem,
) -> None:
    """An item whose adding user was deleted (added_by is null) has no reportable user."""
    other_user_collection_item_fixture.added_by = None
    other_user_collection_item_fixture.save(update_fields=["added_by"])

    payload = {
        "target_type": ReportTargetType.COLLECTION_ITEM_NOTE,
        "target_collection_item": other_user_collection_item_fixture.id,
        "reason": "This note contains harassment.",
    }
    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_rejects_self_report_of_own_collection_item_note(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    collection_owner_fixture: UserModel,
) -> None:
    """A user cannot report their own collection item note, even if they're not the collection's owner."""
    collection = Collection.objects.create(
        name="a collaborative collection",
        user=collection_owner_fixture,
        mode=CollectionMode.COLLABORATIVE,
    )
    own_item = CollectionItem.objects.create(
        collection=collection,
        game=baker.make("games.Game"),
        added_by=user_fixture,
        description="my own note",
    )

    payload = {
        "target_type": ReportTargetType.COLLECTION_ITEM_NOTE,
        "target_collection_item": own_item.id,
        "reason": "I regret writing this.",
    }
    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
