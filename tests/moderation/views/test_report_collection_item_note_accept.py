"""Test accepting a report against a CollectionItem note."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import CollectionItem
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_accept_by_admin_moderates_collection_item_creates_warning_for_added_by(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_collection_item_fixture: CollectionItem,
) -> None:
    """Accepting a pending report against a CollectionItem note moderates it and warns added_by."""
    report = Report.objects.create(
        target_type=ReportTargetType.COLLECTION_ITEM_NOTE,
        target_collection_item=other_user_collection_item_fixture,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_collection_item_fixture.description,
        reason="Harassment.",
    )

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    other_user_collection_item_fixture.refresh_from_db()
    assert other_user_collection_item_fixture.is_moderated is True

    warning = ModerationWarning.objects.get(report=report)
    assert warning.user == other_user_fixture
