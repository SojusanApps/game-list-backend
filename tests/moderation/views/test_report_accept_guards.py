"""Test permission and state guards on ReportViewSet.accept."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from game_list.games.models import GameReview
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_accept_by_non_staff_is_forbidden(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """A non-staff user, including the report's own filer, cannot accept it."""
    report = make_review_report(user_fixture, other_user_game_review_fixture)

    response = authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    report.refresh_from_db()
    assert report.status == Report.Status.PENDING


@pytest.mark.django_db()
def test_accept_of_non_pending_report_is_rejected(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """Accepting a report that is no longer pending (e.g. already rejected) is rejected."""
    report = make_review_report(admin_user_fixture, other_user_game_review_fixture, status=Report.Status.REJECTED)

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert ModerationWarning.objects.filter(report=report).exists() is False
