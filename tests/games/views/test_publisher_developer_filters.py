"""Tests for the publisher/developer name filters on the games and game-lists API endpoints."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import Company, Game, GameList, GameListStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_filter_games_by_publisher_matches_bilingual_name(api_client: APIClient) -> None:
    """Filtering games by publisher matches on either the English or Polish company name."""
    publisher = baker.make(Company, name_en="CD Projekt", name_pl="CD Projekt PL")
    other_publisher = baker.make(Company, name_en="Valve", name_pl="Valve")
    matching_game = baker.make(Game, publisher=publisher)
    baker.make(Game, publisher=other_publisher)

    response = api_client.get(reverse("games:games-list"), {"publisher": "cd projekt"})

    assert response.status_code == status.HTTP_200_OK
    ids = [entry["id"] for entry in response.json()["results"]]
    assert matching_game.id in ids
    assert len(ids) == 1


@pytest.mark.django_db()
def test_filter_games_by_developer_matches_bilingual_name(api_client: APIClient) -> None:
    """Filtering games by developer matches on either the English or Polish company name."""
    developer = baker.make(Company, name_en="CD Projekt Red", name_pl="CD Projekt Red PL")
    other_developer = baker.make(Company, name_en="Valve", name_pl="Valve")
    matching_game = baker.make(Game, developer=developer)
    baker.make(Game, developer=other_developer)

    response = api_client.get(reverse("games:games-list"), {"developer": "cd projekt red"})

    assert response.status_code == status.HTTP_200_OK
    ids = [entry["id"] for entry in response.json()["results"]]
    assert matching_game.id in ids
    assert len(ids) == 1


@pytest.mark.django_db()
def test_filter_gamelist_by_publisher_matches_bilingual_name(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Filtering game-lists by publisher matches on the related game's publisher name."""
    publisher = baker.make(Company, name_en="CD Projekt", name_pl="CD Projekt PL")
    other_publisher = baker.make(Company, name_en="Valve", name_pl="Valve")
    matching_game = baker.make(Game, publisher=publisher)
    other_game = baker.make(Game, publisher=other_publisher)
    matching_entry = baker.make(GameList, game=matching_game, user=user_fixture, status=GameListStatus.PLAYING)
    baker.make(GameList, game=other_game, user=user_fixture, status=GameListStatus.PLAYING)

    response = api_client.get(reverse("games:game-lists-list"), {"publisher": "cd projekt"})

    assert response.status_code == status.HTTP_200_OK
    ids = [entry["id"] for entry in response.json()["results"]]
    assert matching_entry.id in ids
    assert len(ids) == 1


@pytest.mark.django_db()
def test_filter_gamelist_by_developer_matches_bilingual_name(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Filtering game-lists by developer matches on the related game's developer name."""
    developer = baker.make(Company, name_en="CD Projekt Red", name_pl="CD Projekt Red PL")
    other_developer = baker.make(Company, name_en="Valve", name_pl="Valve")
    matching_game = baker.make(Game, developer=developer)
    other_game = baker.make(Game, developer=other_developer)
    matching_entry = baker.make(GameList, game=matching_game, user=user_fixture, status=GameListStatus.PLAYING)
    baker.make(GameList, game=other_game, user=user_fixture, status=GameListStatus.PLAYING)

    response = api_client.get(reverse("games:game-lists-list"), {"developer": "cd projekt red"})

    assert response.status_code == status.HTTP_200_OK
    ids = [entry["id"] for entry in response.json()["results"]]
    assert matching_entry.id in ids
    assert len(ids) == 1
