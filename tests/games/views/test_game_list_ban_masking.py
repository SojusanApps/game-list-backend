"""Wiring check: a banned user's GameList notes are masked for others even if never individually reported."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.masking import MODERATION_PLACEHOLDER_TEXT

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game, GameList
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_banned_users_unreported_game_list_note_is_masked_for_stranger_but_not_owner(
    api_client: APIClient,
    game_list_fixture: GameList,
) -> None:
    """A never-individually-reported note from a banned user is masked for strangers, visible to its owner."""
    owner = game_list_fixture.user
    owner.is_banned = True
    owner.save(update_fields=["is_banned"])
    assert game_list_fixture.is_moderated is False

    stranger: UserModel = owner.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("games:game-lists-detail", kwargs={"pk": game_list_fixture.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["description"] == MODERATION_PLACEHOLDER_TEXT

    api_client.force_authenticate(user=owner)
    owner_response = api_client.get(reverse("games:game-lists-detail", kwargs={"pk": game_list_fixture.id}))
    assert owner_response.status_code == status.HTTP_200_OK
    assert owner_response.data["description"] == game_list_fixture.description


@pytest.mark.django_db()
def test_banned_user_can_still_create_a_game_list_entry_with_a_note(
    api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A banned user can still successfully create a new GameList entry and note - no write-time restriction."""
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])
    api_client.force_authenticate(user=user_fixture)

    response = api_client.post(
        reverse("games:game-lists-list"),
        {
            "game": game_fixture.id,
            "status": "PTP",
            "description": "a note from a banned user",
            "user": user_fixture.id,
            "owned_on": [],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
