"""Wiring check: GameReview listing can be ordered by creation time or by the reviewer's score."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.utils import timezone
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import GameList, GameListStatus, GameReview, GameReviewRecommendation, ReviewLanguage
from game_list.users.models import User

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game


@pytest.fixture
def reviews(game_fixture: Game) -> list[GameReview]:
    """Three reviews, oldest first, whose authors scored the game 5, 9 and not at all."""
    now = timezone.now()
    created = []
    for index, score in enumerate((5, 9, None)):
        user = baker.make(User, username=f"reviewer_{index}")
        baker.make(GameList, user=user, game=game_fixture, score=score, status=GameListStatus.COMPLETED)
        review = baker.make(
            GameReview,
            user=user,
            game=game_fixture,
            recommendation=GameReviewRecommendation.RECOMMENDED,
            language=ReviewLanguage.ENGLISH,
        )
        GameReview.objects.filter(pk=review.pk).update(created_at=now + timedelta(minutes=index))
        created.append(review)
    return created


def _ids(api_client: APIClient, ordering: str) -> list[int]:
    response = api_client.get(reverse("games:game-reviews-list"), {"ordering": ordering})
    assert response.status_code == status.HTTP_200_OK
    return [item["id"] for item in response.data["results"]]


@pytest.mark.django_db()
def test_order_by_newest(api_client: APIClient, reviews: list[GameReview]) -> None:
    """`-created_at` lists the newest review first."""
    assert _ids(api_client, "-created_at") == [r.id for r in reversed(reviews)]


@pytest.mark.django_db()
def test_order_by_highest_score_puts_unscored_last(api_client: APIClient, reviews: list[GameReview]) -> None:
    """`-score` lists the highest reviewer score first and unscored reviews last."""
    assert _ids(api_client, "-score") == [reviews[1].id, reviews[0].id, reviews[2].id]


@pytest.mark.django_db()
def test_order_by_lowest_score_still_puts_unscored_last(api_client: APIClient, reviews: list[GameReview]) -> None:
    """`score` lists the lowest reviewer score first and unscored reviews still last."""
    assert _ids(api_client, "score") == [reviews[0].id, reviews[1].id, reviews[2].id]
