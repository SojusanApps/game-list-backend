"""Test reporting and moderating a CollectionItem note (description)."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.collections.models import CollectionItem
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_report_against_collection_item_note_snapshots_value_and_added_by_not_collection_owner(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    collection_owner_fixture: UserModel,
    other_user_collection_item_fixture: CollectionItem,
) -> None:
    """Reporting a collaborative collection item's note attributes the report to added_by, not the owner."""
    payload = {
        "target_type": ReportTargetType.COLLECTION_ITEM_NOTE,
        "target_collection_item": other_user_collection_item_fixture.id,
        "reason": "This note contains harassment.",
    }

    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    report = Report.objects.get(id=response.data["id"])
    assert report.reported_by == user_fixture
    assert report.reported_user == other_user_fixture
    assert report.reported_user != collection_owner_fixture
    assert report.target_collection_item_id == other_user_collection_item_fixture.id
    assert report.reported_value == other_user_collection_item_fixture.description
    assert report.status == Report.Status.PENDING
