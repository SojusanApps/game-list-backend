"""Tests for the fuzzy game title filter on the game-lists API endpoint."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import Game, GameList, GameListStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_filter_gamelist_by_title_finds_matching_entry(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Filtering game-lists by title fuzzy-matches on the related game's title."""
    matching_game = baker.make(Game, title_en="Half-Life", title_pl="Half-Life")
    other_game = baker.make(Game, title_en="Unrelated Game", title_pl="Unrelated Game")
    baker.make(GameList, game=matching_game, user=user_fixture, status=GameListStatus.PLAYING)
    baker.make(GameList, game=other_game, user=user_fixture, status=GameListStatus.PLAYING)

    response = api_client.get(reverse("games:game-lists-list"), {"title": "half-life"})

    assert response.status_code == status.HTTP_200_OK
    titles = [entry["title"] for entry in response.json()["results"]]
    assert "Half-Life" in titles
    assert "Unrelated Game" not in titles
