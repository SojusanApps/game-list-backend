"""Wiring check: GameReview.recommendation is mandatory on write, filterable, and drives per-game counts."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import GameReview, GameReviewRecommendation, ReviewLanguage

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_without_recommendation_is_rejected(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Omitting recommendation on create is a 400, not a silent default."""
    response = authenticated_api_client.post(
        reverse("games:game-reviews-list"),
        {"game": game_fixture.id, "review": "no opinion given", "user": user_fixture.id},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "recommendation" in response.data


@pytest.mark.django_db()
def test_recommendation_is_editable_after_creation(
    authenticated_api_client: APIClient,
    game_review_fixture: GameReview,
) -> None:
    """A reviewer can change their recommendation after creation, same as review text."""
    authenticated_api_client.force_authenticate(user=game_review_fixture.user)
    response = authenticated_api_client.patch(
        reverse("games:game-reviews-detail", kwargs={"pk": game_review_fixture.id}),
        {"recommendation": GameReviewRecommendation.NOT_RECOMMENDED.value},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    game_review_fixture.refresh_from_db()
    assert game_review_fixture.recommendation == GameReviewRecommendation.NOT_RECOMMENDED


@pytest.mark.django_db()
def test_list_filters_by_recommendation(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """?recommendation= filters to reviews with that exact value."""
    GameReview.objects.create(
        game=game_fixture,
        user=user_fixture,
        recommendation=GameReviewRecommendation.RECOMMENDED,
        language=ReviewLanguage.ENGLISH,
    )
    other_user: UserModel = user_fixture.__class__.objects.create(username="other", email="other@email.com")
    GameReview.objects.create(
        game=game_fixture,
        user=other_user,
        recommendation=GameReviewRecommendation.NOT_RECOMMENDED,
        language=ReviewLanguage.ENGLISH,
    )

    response = authenticated_api_client.get(
        reverse("games:game-reviews-list"),
        {"recommendation": GameReviewRecommendation.NOT_RECOMMENDED.value},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["recommendation"] == GameReviewRecommendation.NOT_RECOMMENDED.value


@pytest.mark.django_db()
def test_recommendation_counts_present_only_when_filtered_by_game(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """The recommendation_counts breakdown is null with no game filter, and covers all 3 values when filtered."""
    other_user: UserModel = user_fixture.__class__.objects.create(username="other", email="other@email.com")
    GameReview.objects.create(
        game=game_fixture,
        user=user_fixture,
        recommendation=GameReviewRecommendation.RECOMMENDED,
        language=ReviewLanguage.ENGLISH,
    )
    GameReview.objects.create(
        game=game_fixture,
        user=other_user,
        recommendation=GameReviewRecommendation.RECOMMENDED,
        language=ReviewLanguage.ENGLISH,
    )

    unfiltered_response = authenticated_api_client.get(reverse("games:game-reviews-list"))
    assert unfiltered_response.data["recommendation_counts"] is None

    filtered_response = authenticated_api_client.get(reverse("games:game-reviews-list"), {"game": game_fixture.id})
    assert filtered_response.data["recommendation_counts"] == {
        GameReviewRecommendation.RECOMMENDED.value: 2,
        GameReviewRecommendation.NOT_RECOMMENDED.value: 0,
        GameReviewRecommendation.UNDECIDED.value: 0,
    }


@pytest.mark.django_db()
def test_recommendation_counts_ignore_the_recommendation_filter_itself(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Adding ?recommendation= alongside ?game= still returns counts for all 3 categories, not just the one."""
    GameReview.objects.create(
        game=game_fixture,
        user=user_fixture,
        recommendation=GameReviewRecommendation.UNDECIDED,
        language=ReviewLanguage.ENGLISH,
    )

    response = authenticated_api_client.get(
        reverse("games:game-reviews-list"),
        {"game": str(game_fixture.id), "recommendation": GameReviewRecommendation.RECOMMENDED.value},
    )

    assert response.data["count"] == 0
    assert response.data["recommendation_counts"] == {
        GameReviewRecommendation.RECOMMENDED.value: 0,
        GameReviewRecommendation.NOT_RECOMMENDED.value: 0,
        GameReviewRecommendation.UNDECIDED.value: 1,
    }
