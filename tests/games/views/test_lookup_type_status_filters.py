"""Tests for the bilingual text filters on the game-types and game-statuses API endpoints."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.games.models import GameStatus, GameType

if TYPE_CHECKING:
    from rest_framework.test import APIClient


@pytest.mark.django_db()
def test_filter_game_types_by_type_matches_bilingual_value(api_client: APIClient) -> None:
    """Filtering game types by `type` matches on either the English or Polish type label."""
    matching = baker.make(GameType, type_en="Main Game", type_pl="Gra główna")
    baker.make(GameType, type_en="DLC", type_pl="DLC")

    response = api_client.get(reverse("games:game-types-list"), {"type": "main game"})

    assert response.status_code == status.HTTP_200_OK
    ids = [entry["id"] for entry in response.json()["results"]]
    assert matching.id in ids
    assert len(ids) == 1


@pytest.mark.django_db()
def test_filter_game_statuses_by_status_matches_bilingual_value(api_client: APIClient) -> None:
    """Filtering game statuses by `status` matches on either the English or Polish status label."""
    matching = baker.make(GameStatus, status_en="Released", status_pl="Wydana")
    baker.make(GameStatus, status_en="Alpha", status_pl="Alfa")

    response = api_client.get(reverse("games:game-statuses-list"), {"status": "released"})

    assert response.status_code == status.HTTP_200_OK
    ids = [entry["id"] for entry in response.json()["results"]]
    assert matching.id in ids
    assert len(ids) == 1
