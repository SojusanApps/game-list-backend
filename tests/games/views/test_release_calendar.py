"""Tests for the release_calendar endpoint on GameViewSet."""

import datetime
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from game_list.games.models import Game, GameStats

if TYPE_CHECKING:
    from rest_framework.test import APIClient


@pytest.fixture
def calendar_games() -> list[Game]:
    """Create games to test calendar."""
    games = []

    # 2024-01-01 -> 3 games (to test limits)
    for i in range(3):
        game1: Game = baker.make("games.Game", release_date=datetime.date(2024, 1, 1))
        # Update existing auto-created GameStats
        GameStats.objects.filter(game=game1).update(members_count=(i + 1) * 10, popularity=(i + 1) * 10)
        games.append(game1)

    # 2024-01-02 -> 1 game
    game2: Game = baker.make("games.Game", release_date=datetime.date(2024, 1, 2))
    GameStats.objects.filter(game=game2).update(members_count=50, popularity=50)
    games.append(game2)

    # 2024-01-03 -> 2 games
    for i in range(2):
        game3: Game = baker.make("games.Game", release_date=datetime.date(2024, 1, 3))
        GameStats.objects.filter(game=game3).update(members_count=(i + 1) * 5, popularity=(i + 1) * 5)
        games.append(game3)

    return games


@pytest.mark.django_db()
def test_release_calendar_dates_and_limit(api_client: APIClient, calendar_games: list[Game]) -> None:  # noqa: ARG001
    """Test that calendar returns max 2 games per day ordered by stats__popularity."""
    url = reverse("games:games-release-calendar")

    response = api_client.get(url, {"start_date": "2024-01-01", "end_date": "2024-01-02"})

    assert response.status_code == status.HTTP_200_OK
    results = response.json()

    # 2024-01-01 has 3 games, all 3 returned (limit is MAX_GAMES_PER_DAY_IN_CALENDAR=3)
    # 2024-01-02 has 1 game
    # Total returned: 4 games
    assert len(results) == 4  # noqa: PLR2004

    dates_counter: dict[str, int] = {}
    for item in results:
        dates_counter[item["release_date"]] = dates_counter.get(item["release_date"], 0) + 1

    assert dates_counter["2024-01-01"] == 3  # noqa: PLR2004
    assert dates_counter["2024-01-02"] == 1
    assert "2024-01-03" not in dates_counter

    # Check ordering: it should order by release_date asc, popularity desc
    assert results[0]["release_date"] == "2024-01-01"
    # highest popularity first
    assert results[0]["popularity"] == 30  # noqa: PLR2004
    assert results[1]["popularity"] == 20  # noqa: PLR2004
    assert results[2]["popularity"] == 10  # noqa: PLR2004
    assert results[3]["release_date"] == "2024-01-02"


@pytest.mark.django_db()
def test_release_calendar_missing_dates(api_client: APIClient) -> None:
    """Test that start_date and end_date are required."""
    url = reverse("games:games-release-calendar")

    # Missing both
    response = api_client.get(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Missing end_date
    response = api_client.get(url, {"start_date": "2024-01-01"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Missing start_date
    response = api_client.get(url, {"end_date": "2024-01-31"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_release_calendar_invalid_date_format(api_client: APIClient) -> None:
    """Test invalid date formats."""
    url = reverse("games:games-release-calendar")
    response = api_client.get(url, {"start_date": "invalid", "end_date": "2024-01-31"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_release_calendar_exceeds_max_span(api_client: APIClient) -> None:
    """Test that the endpoint prevents a date span > 31 days."""
    url = reverse("games:games-release-calendar")

    # 32 days span (Jan 1 to Feb 2)
    response = api_client.get(url, {"start_date": "2024-01-01", "end_date": "2024-02-02"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "The date range must be between 0 and 31 days."

    # Negative span
    response = api_client.get(url, {"start_date": "2024-01-02", "end_date": "2024-01-01"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "The date range must be between 0 and 31 days."

    # Exactly 31 days span (Jan 1 to Feb 1 is 31 days)
    response = api_client.get(url, {"start_date": "2024-01-01", "end_date": "2024-02-01"})
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_infinite_list_multiple_orderings(api_client: APIClient, calendar_games: list[Game]) -> None:  # noqa: ARG001
    """Test that infinite lists can use multiple ordering fields, such as `release_date,-stats__popularity`."""
    url = reverse("games:games-list")

    response = api_client.get(url, {"ordering": "release_date,-popularity"})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    results = data.get("results", data)

    # All 6 games should be returned
    assert len(results) == 6  # noqa: PLR2004

    # 2024-01-01
    assert results[0]["release_date"] == "2024-01-01"
    assert results[0]["popularity"] == 30  # noqa: PLR2004
    assert results[1]["popularity"] == 20  # noqa: PLR2004
    assert results[2]["popularity"] == 10  # noqa: PLR2004

    # 2024-01-02
    assert results[3]["release_date"] == "2024-01-02"

    # 2024-01-03
    assert results[4]["release_date"] == "2024-01-03"
    assert results[4]["popularity"] == 10  # noqa: PLR2004
    assert results[5]["popularity"] == 5  # noqa: PLR2004
