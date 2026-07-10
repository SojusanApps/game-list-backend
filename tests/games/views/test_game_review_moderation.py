"""Wiring check: GameReviewSerializer.review goes through the shared moderation masking helper."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.moderation.masking import MODERATION_PLACEHOLDER_TEXT

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import GameReview
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_moderated_review_shows_placeholder_to_stranger_and_real_text_to_owner(
    api_client: APIClient,
    user_fixture: UserModel,
    game_review_fixture: GameReview,
) -> None:
    """A review flagged is_moderated shows the placeholder to a stranger but the real text to its owner."""
    game_review_fixture.is_moderated = True
    game_review_fixture.save(update_fields=["is_moderated"])

    stranger: UserModel = user_fixture.__class__.objects.create(
        username="stranger",
        email="stranger@email.com",
    )
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(
        reverse("games:game-reviews-detail", kwargs={"pk": game_review_fixture.id}),
    )
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["review"] == MODERATION_PLACEHOLDER_TEXT

    api_client.force_authenticate(user=game_review_fixture.user)
    owner_response = api_client.get(
        reverse("games:game-reviews-detail", kwargs={"pk": game_review_fixture.id}),
    )
    assert owner_response.status_code == status.HTTP_200_OK
    assert owner_response.data["review"] == game_review_fixture.review
