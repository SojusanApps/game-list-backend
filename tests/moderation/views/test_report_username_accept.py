"""Test accepting a report against a User's username."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_accept_by_admin_sets_has_moderated_username_creates_warning_and_notifies(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Accepting a pending username report sets User.has_moderated_username; the live username is untouched."""
    original_username = other_user_fixture.username
    report = Report.objects.create(
        target_type=ReportTargetType.USERNAME,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=original_username,
        reason="Offensive username.",
    )

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    other_user_fixture.refresh_from_db()
    assert other_user_fixture.has_moderated_username is True
    assert other_user_fixture.username == original_username

    warning = ModerationWarning.objects.get(report=report)
    assert warning.user == other_user_fixture
