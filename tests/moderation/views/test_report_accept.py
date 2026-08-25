"""Test the accept action on ReportViewSet."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report
from game_list.notifications.constants import NotificationCategory
from game_list.notifications.models import Notification

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from game_list.games.models import GameReview
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_accept_by_admin_moderates_review_creates_warning_and_notifies(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """An admin accepting a pending report moderates the review, issues a warning, and notifies the owner."""
    report = make_review_report(admin_user_fixture, other_user_game_review_fixture)

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    other_user_game_review_fixture.refresh_from_db()
    assert other_user_game_review_fixture.is_moderated is True

    report.refresh_from_db()
    assert report.status == Report.StatusChoices.ACCEPTED
    assert report.reviewed_by == admin_user_fixture
    assert report.reviewed_at is not None

    warning = ModerationWarning.objects.get(report=report)
    assert warning.user == other_user_fixture
    assert warning.issued_by == admin_user_fixture

    notification = Notification.objects.get(recipient=other_user_fixture, category=NotificationCategory.MODERATION)
    assert notification.actor == admin_user_fixture
