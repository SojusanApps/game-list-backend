"""Tests for the fuzzy game title filter via the games API endpoint."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.games.models import Game

if TYPE_CHECKING:
    from rest_framework.test import APIClient


@pytest.mark.django_db()
def test_filter_by_title_finds_game_with_exact_lowercase_query(api_client: APIClient) -> None:
    """Searching by lowercase slug-style title finds the game — tracer bullet."""
    baker.make(Game, title_en="Half-Life", title_pl="Half-Life")
    baker.make(Game, title_en="Unrelated Game", title_pl="Unrelated Game")

    response = api_client.get(reverse("games:games-list"), {"title": "half-life"})

    assert response.status_code == status.HTTP_200_OK
    titles = [r["title"] for r in response.json()["results"]]
    assert "Half-Life" in titles
    assert "Unrelated Game" not in titles


@pytest.mark.django_db()
def test_filter_by_title_finds_game_with_typo(api_client: APIClient) -> None:
    """A one-character typo still returns the correct game (fuzzy search)."""
    baker.make(Game, title_en="Half-Life", title_pl="Half-Life")

    response = api_client.get(reverse("games:games-list"), {"title": "haf lif"})

    assert response.status_code == status.HTTP_200_OK
    titles = [r["title"] for r in response.json()["results"]]
    assert "Half-Life" in titles


@pytest.mark.django_db()
def test_filter_by_title_ignores_diacritics(api_client: APIClient) -> None:
    """Searching without diacritics still finds a game whose title has them."""
    baker.make(Game, title_en="The Witcher", title_pl="Wiedźmin")

    response = api_client.get(reverse("games:games-list"), {"title": "wiedzmin"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] >= 1


@pytest.mark.django_db()
def test_filter_by_title_matches_fragment(api_client: APIClient) -> None:
    """A single word from a multi-word title returns the game."""
    baker.make(Game, title_en="The Witcher 3: Wild Hunt", title_pl="Wiedźmin 3: Dziki Gon")

    response = api_client.get(reverse("games:games-list"), {"title": "witcher"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] >= 1


@pytest.mark.django_db()
def test_filter_by_title_is_word_order_independent(api_client: APIClient) -> None:
    """Reversed word order still matches the correct game."""
    baker.make(Game, title_en="Half-Life", title_pl="Half-Life")

    response = api_client.get(reverse("games:games-list"), {"title": "life half"})

    assert response.status_code == status.HTTP_200_OK
    titles = [r["title"] for r in response.json()["results"]]
    assert "Half-Life" in titles


@pytest.mark.django_db()
def test_filter_by_title_searches_polish_title(api_client: APIClient) -> None:
    """Querying with the Polish title finds a game that has no matching English title."""
    baker.make(Game, title_en="The Witcher", title_pl="Wiedźmin")

    response = api_client.get(reverse("games:games-list"), {"title": "wiedzmin"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] >= 1


@pytest.mark.django_db()
def test_filter_by_title_ranks_misspelled_title_above_shorter_lookalike(api_client: APIClient) -> None:
    """A transposition typo ranks the intended game above shorter lookalike titles.

    Trigram similarity alone scores "the witchre" higher against "The Witch..." titles
    than against "The Witcher..." ones; the Damerau-Levenshtein re-ranking must not.
    """
    baker.make(Game, title_en="The Witch's House", title_pl="The Witch's House")
    baker.make(Game, title_en="The Witcher 3: Wild Hunt", title_pl="Wiedźmin 3: Dziki Gon")

    response = api_client.get(reverse("games:games-list"), {"title": "the witchre"})

    assert response.status_code == status.HTTP_200_OK
    titles = [r["title"] for r in response.json()["results"]]
    assert titles[0] == "The Witcher 3: Wild Hunt"


@pytest.mark.django_db()
def test_filter_by_title_puts_exact_match_before_partial_matches(api_client: APIClient) -> None:
    """An exact title match outranks games whose titles merely contain the query."""
    baker.make(Game, title_en="The Witcher 3: Wild Hunt", title_pl="Wiedźmin 3: Dziki Gon")
    baker.make(Game, title_en="The Witcher", title_pl="Wiedźmin")

    response = api_client.get(reverse("games:games-list"), {"title": "The Witcher"})

    assert response.status_code == status.HTTP_200_OK
    titles = [r["title"] for r in response.json()["results"]]
    assert titles[0] == "The Witcher"
    assert "The Witcher 3: Wild Hunt" in titles


@pytest.mark.django_db()
def test_filter_by_title_breaks_ties_by_members_count(api_client: APIClient) -> None:
    """Among equally good prefix matches, the game with more members comes first."""
    niche = baker.make(Game, title_en="The Witch's House", title_pl="The Witch's House")
    popular = baker.make(Game, title_en="The Witcher 3: Wild Hunt", title_pl="Wiedźmin 3: Dziki Gon")
    niche.stats.members_count = 5
    niche.stats.save()
    popular.stats.members_count = 1000
    popular.stats.save()

    response = api_client.get(reverse("games:games-list"), {"title": "the witc"})

    assert response.status_code == status.HTTP_200_OK
    titles = [r["title"] for r in response.json()["results"]]
    assert titles[0] == "The Witcher 3: Wild Hunt"


@pytest.mark.django_db()
def test_filter_by_title_returns_empty_for_unrelated_query(api_client: APIClient) -> None:
    """A completely unrelated query returns no results."""
    baker.make(Game, title_en="Half-Life", title_pl="Half-Life")

    response = api_client.get(reverse("games:games-list"), {"title": "xyzxyzxyz"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] == 0
