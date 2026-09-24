"""Wiring check: GameReview.language is mandatory on write, editable, filterable and never masked."""

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
def test_create_without_language_is_rejected(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Omitting language on create is a 400, not a silent default."""
    response = authenticated_api_client.post(
        reverse("games:game-reviews-list"),
        {
            "game": game_fixture.id,
            "review": "no language given",
            "recommendation": GameReviewRecommendation.RECOMMENDED.value,
            "user": user_fixture.id,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "language" in response.data


@pytest.mark.django_db()
def test_create_with_unsupported_language_is_rejected(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Only English and Polish are accepted."""
    response = authenticated_api_client.post(
        reverse("games:game-reviews-list"),
        {
            "game": game_fixture.id,
            "review": "bonjour",
            "recommendation": GameReviewRecommendation.RECOMMENDED.value,
            "language": "fr",
            "user": user_fixture.id,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "language" in response.data


@pytest.mark.django_db()
def test_language_is_editable_after_creation(
    authenticated_api_client: APIClient,
    game_review_fixture: GameReview,
) -> None:
    """A reviewer can change the language of their one review, same as its text."""
    response = authenticated_api_client.patch(
        reverse("games:game-reviews-detail", kwargs={"pk": game_review_fixture.id}),
        {"language": ReviewLanguage.POLISH.value},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    game_review_fixture.refresh_from_db()
    assert game_review_fixture.language == ReviewLanguage.POLISH


@pytest.mark.django_db()
def test_list_filters_by_language(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """?language= filters to reviews in that language; no param returns every language."""
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
        recommendation=GameReviewRecommendation.RECOMMENDED,
        language=ReviewLanguage.POLISH,
    )

    polish = authenticated_api_client.get(reverse("games:game-reviews-list"), {"language": "pl"})
    unfiltered = authenticated_api_client.get(reverse("games:game-reviews-list"))

    assert polish.status_code == status.HTTP_200_OK
    assert polish.data["count"] == 1
    assert polish.data["results"][0]["language"] == ReviewLanguage.POLISH.value
    assert unfiltered.data["count"] == 2  # noqa: PLR2004


@pytest.mark.django_db()
def test_list_with_invalid_language_filter_is_rejected(authenticated_api_client: APIClient) -> None:
    """An unknown ?language= value is a 400."""
    response = authenticated_api_client.get(reverse("games:game-reviews-list"), {"language": "fr"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
