"""Test accepting a report against a User's avatar."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_accept_by_admin_sets_has_moderated_avatar_creates_warning_and_notifies(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Accepting a pending avatar report sets User.has_moderated_avatar and issues a warning."""
    report = Report.objects.create(
        target_type=ReportTargetType.AVATAR,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value="",
        reason="Illegal content.",
    )

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    other_user_fixture.refresh_from_db()
    assert other_user_fixture.has_moderated_avatar is True

    warning = ModerationWarning.objects.get(report=report)
    assert warning.user == other_user_fixture
