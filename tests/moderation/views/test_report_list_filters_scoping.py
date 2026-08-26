"""Test that filters compose with (don't bypass) the non-staff visibility scoping on ReportViewSet.list."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_non_staff_reported_user_filter_cannot_surface_others_reports(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """A non-staff user filtering by reported_user still only sees reports they personally filed."""
    someone_elses_report = Report.objects.create(
        target_type=ReportTargetType.USERNAME,
        reported_by=other_user_fixture,
        reported_user=user_fixture,
        reported_value=user_fixture.username,
        reason="Filed by someone else, must not leak via the reported_user filter.",
    )

    response = authenticated_api_client.get(
        reverse("moderation:reports-list"),
        {"reported_user": user_fixture.id},
    )

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {entry["id"] for entry in response.data["results"]}
    assert someone_elses_report.id not in returned_ids
    assert response.data["results"] == []
