"""Test ReportViewSet.direct_moderate: the admin fast lane that bypasses the pending queue."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import GameReview
from game_list.moderation.models import ModerationWarning, Report, ReportTargetType
from game_list.notifications.constants import NotificationCategory, NotificationVerb
from game_list.notifications.models import Notification

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_direct_moderate_flags_target_issues_warning_and_notifies(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """A direct-moderate call moderates the target immediately, without a pending Report ever existing."""
    payload = {
        "target_type": ReportTargetType.REVIEW,
        "target_review": other_user_game_review_fixture.id,
        "reason": "Harassment, acting on a support ticket.",
    }

    response = admin_authenticated_api_client.post(
        reverse("moderation:reports-direct-moderate"),
        payload,
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    other_user_game_review_fixture.refresh_from_db()
    assert other_user_game_review_fixture.is_moderated is True

    report = Report.objects.get(id=response.data["id"])
    assert report.status == Report.Status.ACCEPTED
    assert report.source == Report.Source.ADMIN_DIRECT
    assert report.reported_by == admin_user_fixture
    assert report.reported_user == other_user_fixture

    warning = ModerationWarning.objects.get(report=report)
    assert warning.user == other_user_fixture

    notification = Notification.objects.get(
        recipient=other_user_fixture,
        category=NotificationCategory.MODERATION,
        verb=NotificationVerb.WARNING_ISSUED,
    )
    assert notification.actor == admin_user_fixture


@pytest.mark.django_db()
def test_direct_moderate_sweeps_other_pending_reports_without_extra_warning(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """Other pending reports on the exact same target are auto-accepted, but issue no additional warning."""
    sibling_report = make_review_report(user_fixture, other_user_game_review_fixture)

    response = admin_authenticated_api_client.post(
        reverse("moderation:reports-direct-moderate"),
        {
            "target_type": ReportTargetType.REVIEW,
            "target_review": other_user_game_review_fixture.id,
            "reason": "Harassment.",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    sibling_report.refresh_from_db()
    assert sibling_report.status == Report.Status.ACCEPTED
    assert sibling_report.reviewed_by == admin_user_fixture
    assert ModerationWarning.objects.filter(report=sibling_report).exists() is False
    assert ModerationWarning.objects.filter(user=other_user_fixture).count() == 1


@pytest.mark.django_db()
def test_direct_moderate_rejects_already_moderated_target(
    admin_authenticated_api_client: APIClient,
    other_user_game_review_fixture: GameReview,
) -> None:
    """Direct-moderating a target that's already flagged as moderated is rejected: nothing to do."""
    other_user_game_review_fixture.is_moderated = True
    other_user_game_review_fixture.save(update_fields=["is_moderated"])

    response = admin_authenticated_api_client.post(
        reverse("moderation:reports-direct-moderate"),
        {
            "target_type": ReportTargetType.REVIEW,
            "target_review": other_user_game_review_fixture.id,
            "reason": "Harassment.",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_direct_moderate_rejects_staff_target(
    admin_authenticated_api_client: APIClient,
) -> None:
    """Direct-moderating content owned by a staff user is refused, even by a different admin."""
    other_staff_user: UserModel = baker.make("users.User", username="other_staff", is_staff=True)
    review = GameReview.objects.create(
        review="a staff member's review",
        recommendation=GameReview.Recommendation.UNDECIDED,
        game=baker.make("games.Game"),
        user=other_staff_user,
    )

    response = admin_authenticated_api_client.post(
        reverse("moderation:reports-direct-moderate"),
        {
            "target_type": ReportTargetType.REVIEW,
            "target_review": review.id,
            "reason": "Harassment.",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    review.refresh_from_db()
    assert review.is_moderated is False


@pytest.mark.django_db()
def test_direct_moderate_by_non_staff_is_forbidden(
    authenticated_api_client: APIClient,
    other_user_game_review_fixture: GameReview,
) -> None:
    """A non-staff user cannot use the direct-moderation fast lane."""
    response = authenticated_api_client.post(
        reverse("moderation:reports-direct-moderate"),
        {
            "target_type": ReportTargetType.REVIEW,
            "target_review": other_user_game_review_fixture.id,
            "reason": "Harassment.",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
