"""Test accepting a report against a Collection."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import Collection
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_accept_by_admin_moderates_collection_creates_warning_and_notifies(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_collection_fixture: Collection,
) -> None:
    """Accepting a pending report against a Collection moderates it (both fields) and issues a warning."""
    report = Report.objects.create(
        target_type=ReportTargetType.COLLECTION,
        target_collection=other_user_collection_fixture,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=f"name: {other_user_collection_fixture.name}\ndescription: "
        f"{other_user_collection_fixture.description}",
        reason="Harassment.",
    )

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    other_user_collection_fixture.refresh_from_db()
    assert other_user_collection_fixture.is_moderated is True

    warning = ModerationWarning.objects.get(report=report)
    assert warning.user == other_user_fixture
