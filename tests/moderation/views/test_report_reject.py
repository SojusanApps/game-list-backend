"""Test the reject action on ReportViewSet."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report
from game_list.notifications.models import Notification

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from game_list.games.models import GameReview
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_reject_by_admin_has_no_side_effects_besides_status(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """Rejecting a report changes only status/reviewed_by/reviewed_at/rejection_reason."""
    report = make_review_report(admin_user_fixture, other_user_game_review_fixture)

    response = admin_authenticated_api_client.post(
        reverse("moderation:reports-reject", kwargs={"pk": report.id}),
        {"rejection_reason": "Not actually a violation."},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    report.refresh_from_db()
    assert report.status == Report.StatusChoices.REJECTED
    assert report.reviewed_by == admin_user_fixture
    assert report.reviewed_at is not None
    assert report.rejection_reason == "Not actually a violation."

    other_user_game_review_fixture.refresh_from_db()
    assert other_user_game_review_fixture.is_moderated is False
    assert ModerationWarning.objects.filter(report=report).exists() is False
    assert Notification.objects.filter(recipient=other_user_fixture).exists() is False


@pytest.mark.django_db()
def test_reject_of_non_pending_report_is_rejected(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """Rejecting a report that is no longer pending (e.g. already accepted) is rejected."""
    report = make_review_report(
        admin_user_fixture,
        other_user_game_review_fixture,
        status=Report.StatusChoices.ACCEPTED,
    )

    response = admin_authenticated_api_client.post(reverse("moderation:reports-reject", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    report.refresh_from_db()
    assert report.status == Report.StatusChoices.ACCEPTED


@pytest.mark.django_db()
def test_reject_by_non_staff_is_forbidden(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """A non-staff user, including the report's own filer, cannot reject it."""
    report = make_review_report(user_fixture, other_user_game_review_fixture)

    response = authenticated_api_client.post(reverse("moderation:reports-reject", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    report.refresh_from_db()
    assert report.status == Report.StatusChoices.PENDING
