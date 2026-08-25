"""Test ReportViewSet.create validation: self-reports and duplicate pending reports are rejected."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import GameReview
from game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_rejects_self_report(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A user cannot report their own review."""
    game: Game = baker.make("games.Game")
    own_review = GameReview.objects.create(
        review="my own review",
        recommendation=GameReview.Recommendation.RECOMMENDED,
        game=game,
        user=user_fixture,
    )

    payload = {
        "target_type": ReportTargetType.REVIEW,
        "target_review": own_review.id,
        "reason": "I regret writing this.",
    }
    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_rejects_second_pending_report_from_same_reporter_same_review(
    authenticated_api_client: APIClient,
    other_user_game_review_fixture: GameReview,
) -> None:
    """A second pending report from the same reporter against the same review is rejected."""
    payload = {
        "target_type": ReportTargetType.REVIEW,
        "target_review": other_user_game_review_fixture.id,
        "reason": "First report.",
    }
    first_response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")
    assert first_response.status_code == status.HTTP_201_CREATED

    second_response = authenticated_api_client.post(
        reverse("moderation:reports-list"),
        {**payload, "reason": "Second report."},
        format="json",
    )

    assert second_response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_allows_independent_report_from_different_reporter_same_review(
    api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """A different reporter may file their own independent pending report against the same review."""
    payload = {
        "target_type": ReportTargetType.REVIEW,
        "target_review": other_user_game_review_fixture.id,
        "reason": "First reporter's reason.",
    }
    api_client.force_authenticate(user=user_fixture)
    first_response = api_client.post(reverse("moderation:reports-list"), payload, format="json")
    assert first_response.status_code == status.HTTP_201_CREATED

    api_client.force_authenticate(user=admin_user_fixture)
    second_response = api_client.post(
        reverse("moderation:reports-list"),
        {**payload, "reason": "Second reporter's reason."},
        format="json",
    )

    assert second_response.status_code == status.HTTP_201_CREATED
    assert (
        Report.objects.filter(
            target_review=other_user_game_review_fixture,
            status=Report.StatusChoices.PENDING,
        ).count()
        == 2  # noqa: PLR2004
    )
