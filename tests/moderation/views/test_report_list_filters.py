"""Test filtering on ReportViewSet.list."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from my_game_list.games.models import GameReview
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_list_filters_by_target_type_status_reported_by_and_reported_user(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """Staff can filter the report queue by target_type, status, reported_by, and reported_user."""
    target = make_review_report(admin_user_fixture, other_user_game_review_fixture)
    wrong_target_type = Report.objects.create(
        target_type=ReportTargetType.USERNAME,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_fixture.username,
        reason="Different target_type, must not match.",
    )
    wrong_status = Report.objects.create(
        target_type=ReportTargetType.REVIEW,
        target_review=other_user_game_review_fixture,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_game_review_fixture.review,
        reason="Different status, must not match.",
        status=Report.Status.REJECTED,
    )
    wrong_reported_user = Report.objects.create(
        target_type=ReportTargetType.USERNAME,
        reported_by=admin_user_fixture,
        reported_user=admin_user_fixture.__class__.objects.create(username="third_user", email="third@email.com"),
        reported_value="third_user",
        reason="Different reported_user, must not match.",
    )

    response = admin_authenticated_api_client.get(
        reverse("moderation:reports-list"),
        {
            "target_type": str(ReportTargetType.REVIEW),
            "status": str(Report.Status.PENDING),
            "reported_by": str(admin_user_fixture.id),
            "reported_user": str(other_user_fixture.id),
        },
    )

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {entry["id"] for entry in response.data["results"]}
    assert returned_ids == {target.id}
    assert wrong_target_type.id not in returned_ids
    assert wrong_status.id not in returned_ids
    assert wrong_reported_user.id not in returned_ids
