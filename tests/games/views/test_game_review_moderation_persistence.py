"""Wiring check: moderation state on GameReview survives edits, and banned users can still write reviews."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game, GameReview
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_editing_a_moderated_review_does_not_clear_is_moderated(
    api_client: APIClient,
    game_review_fixture: GameReview,
) -> None:
    """Editing an already-moderated review's text does not un-flag it."""
    game_review_fixture.is_moderated = True
    game_review_fixture.save(update_fields=["is_moderated"])

    api_client.force_authenticate(user=game_review_fixture.user)
    response = api_client.patch(
        reverse("games:game-reviews-detail", kwargs={"pk": game_review_fixture.id}),
        {"review": "cleaned up text"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    game_review_fixture.refresh_from_db()
    assert game_review_fixture.review == "cleaned up text"
    assert game_review_fixture.is_moderated is True


@pytest.mark.django_db()
def test_banned_user_can_still_create_a_review(
    api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A banned user can still successfully create a new GameReview - no write-time restriction."""
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])
    api_client.force_authenticate(user=user_fixture)

    response = api_client.post(
        reverse("games:game-reviews-list"),
        {
            "game": game_fixture.id,
            "review": "a review from a banned user",
            "recommendation": "recommended",
            "language": "en",
            "user": user_fixture.id,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
