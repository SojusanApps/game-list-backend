"""Wiring check: GameListSerializer.description goes through the shared moderation masking helper."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.moderation.masking import MODERATION_PLACEHOLDER_TEXT

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import GameList
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_moderated_game_list_note_shows_placeholder_to_stranger_but_not_owner_and_other_fields_untouched(
    api_client: APIClient,
    user_fixture: UserModel,
    game_list_fixture: GameList,
) -> None:
    """A GameList flagged is_moderated masks description for a stranger; other fields stay visible."""
    game_list_fixture.is_moderated = True
    game_list_fixture.save(update_fields=["is_moderated"])

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(reverse("games:game-lists-detail", kwargs={"pk": game_list_fixture.id}))
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["description"] == MODERATION_PLACEHOLDER_TEXT
    assert stranger_response.data["score"] == game_list_fixture.score
    assert stranger_response.data["status_code"] == game_list_fixture.status

    api_client.force_authenticate(user=game_list_fixture.user)
    owner_response = api_client.get(reverse("games:game-lists-detail", kwargs={"pk": game_list_fixture.id}))
    assert owner_response.status_code == status.HTTP_200_OK
    assert owner_response.data["description"] == game_list_fixture.description
