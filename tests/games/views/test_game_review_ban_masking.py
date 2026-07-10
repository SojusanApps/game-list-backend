"""Wiring check: a banned user's reviews are masked for other viewers even if never individually reported."""

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
def test_banned_users_unreported_review_is_masked_for_stranger_but_not_owner(
    api_client: APIClient,
    game_review_fixture: GameReview,
) -> None:
    """A never-individually-reported review from a banned user is masked for strangers, visible to its owner."""
    owner = game_review_fixture.user
    owner.is_banned = True
    owner.save(update_fields=["is_banned"])
    assert game_review_fixture.is_moderated is False

    stranger: UserModel = owner.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("games:game-reviews-detail", kwargs={"pk": game_review_fixture.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["review"] == MODERATION_PLACEHOLDER_TEXT

    api_client.force_authenticate(user=owner)
    owner_response = api_client.get(reverse("games:game-reviews-detail", kwargs={"pk": game_review_fixture.id}))
    assert owner_response.status_code == status.HTTP_200_OK
    assert owner_response.data["review"] == game_review_fixture.review
