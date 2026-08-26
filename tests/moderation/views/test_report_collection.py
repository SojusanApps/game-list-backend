"""Test reporting and moderating a Collection (name + description as one unit)."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import Collection
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_report_against_collection_snapshots_name_and_description_and_owner(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_collection_fixture: Collection,
) -> None:
    """Reporting another user's collection creates a pending Report snapshotting both name and description."""
    payload = {
        "target_type": ReportTargetType.COLLECTION,
        "target_collection": other_user_collection_fixture.id,
        "reason": "This collection contains harassment.",
    }

    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    report = Report.objects.get(id=response.data["id"])
    assert report.reported_by == user_fixture
    assert report.reported_user == other_user_collection_fixture.user
    assert report.target_collection_id == other_user_collection_fixture.id
    assert other_user_collection_fixture.name in report.reported_value
    assert other_user_collection_fixture.description in report.reported_value
    assert report.status == Report.StatusChoices.PENDING
