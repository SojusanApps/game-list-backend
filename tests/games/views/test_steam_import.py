"""Test the steam-import endpoint on GameListViewSet."""

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.cache import cache
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import ExternalGame, ExternalGameSource, Game, GameList, GameListStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


STEAM_PROFILE_ID = "76561198000000001"


def _steam_response(games: list[dict[str, Any]]) -> MagicMock:
    """Build a mock requests.Response for the Steam API."""
    mock = MagicMock()
    mock.json.return_value = {"response": {"game_count": len(games), "games": games}}
    mock.raise_for_status = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """Clear the Django cache before each test to prevent cache leakage between tests."""
    cache.clear()


@pytest.mark.django_db()
def test_steam_import_unauthenticated(api_client: APIClient) -> None:
    """Unauthenticated request returns 401."""
    response = api_client.get(reverse("games:game-lists-steam-import"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_steam_import_missing_steam_profile_id(api_client: APIClient, user_fixture: UserModel) -> None:
    """Missing steam_profile_id query param returns 400."""
    api_client.force_authenticate(user=user_fixture)
    response = api_client.get(reverse("games:game-lists-steam-import"))
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_steam_import_empty_library(api_client: APIClient, user_fixture: UserModel) -> None:
    """Steam returns an empty game list → matched and not_found are both empty."""
    api_client.force_authenticate(user=user_fixture)
    with patch("game_list.games.views.requests.get", return_value=_steam_response([])):
        response = api_client.get(
            reverse("games:game-lists-steam-import"),
            {"steam_profile_id": STEAM_PROFILE_ID},
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"matched": [], "not_found": [], "total_imported": 0}


@pytest.mark.django_db()
def test_steam_import_returns_502_when_steam_api_request_fails(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A RequestException while calling the Steam API returns 502 with a descriptive detail message."""
    api_client.force_authenticate(user=user_fixture)
    failing_response = MagicMock()
    failing_response.raise_for_status.side_effect = requests.RequestException("boom")
    with patch("game_list.games.views.requests.get", return_value=failing_response):
        response = api_client.get(
            reverse("games:game-lists-steam-import"),
            {"steam_profile_id": STEAM_PROFILE_ID},
        )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert STEAM_PROFILE_ID in response.json()["detail"]


@pytest.mark.django_db()
def test_steam_import_unmatched_game_with_steam_source_present_appears_in_not_found(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """When a Steam source exists but a Steam game has no matching ExternalGame, it lands in not_found."""
    baker.make("games.ExternalGameSource", name="Steam")

    api_client.force_authenticate(user=user_fixture)
    with patch(
        "game_list.games.views.requests.get",
        return_value=_steam_response([{"appid": 999, "name": "Some Unmatched Game"}]),
    ):
        response = api_client.get(
            reverse("games:game-lists-steam-import"),
            {"steam_profile_id": STEAM_PROFILE_ID},
        )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matched"] == []
    assert data["not_found"] == [{"appid": 999, "name": "Some Unmatched Game"}]


@pytest.mark.django_db()
def test_steam_import_matched_game_appears_in_matched(api_client: APIClient, user_fixture: UserModel) -> None:
    """A Steam game with a matching ExternalGame (Steam source), not yet in user's list, appears in matched."""
    steam_source: ExternalGameSource = baker.make("games.ExternalGameSource", name="Steam")
    external_game: ExternalGame = baker.make("games.ExternalGame", external_game_source=steam_source, external_id="730")
    game: Game = baker.make("games.Game")
    game.external_games.add(external_game)

    api_client.force_authenticate(user=user_fixture)
    with patch(
        "game_list.games.views.requests.get",
        return_value=_steam_response([{"appid": 730, "name": "Counter-Strike 2"}]),
    ):
        response = api_client.get(
            reverse("games:game-lists-steam-import"),
            {"steam_profile_id": STEAM_PROFILE_ID},
        )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["matched"]) == 1
    assert data["matched"][0]["id"] == game.id
    assert data["not_found"] == []
    assert data["total_imported"] == 1


@pytest.mark.django_db()
def test_steam_import_excludes_already_in_gamelist(api_client: APIClient, user_fixture: UserModel) -> None:
    """A Steam game already in the user's GameList is excluded from matched."""
    steam_source: ExternalGameSource = baker.make("games.ExternalGameSource", name="Steam")
    external_game: ExternalGame = baker.make("games.ExternalGame", external_game_source=steam_source, external_id="730")
    game: Game = baker.make("games.Game")
    game.external_games.add(external_game)
    baker.make(GameList, game=game, user=user_fixture, status=GameListStatus.COMPLETED)

    api_client.force_authenticate(user=user_fixture)
    with patch(
        "game_list.games.views.requests.get",
        return_value=_steam_response([{"appid": 730, "name": "Counter-Strike 2"}]),
    ):
        response = api_client.get(
            reverse("games:game-lists-steam-import"),
            {"steam_profile_id": STEAM_PROFILE_ID},
        )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matched"] == []
    assert data["not_found"] == []
    assert data["total_imported"] == 1


@pytest.mark.django_db()
def test_steam_import_unmatched_game_appears_in_not_found(api_client: APIClient, user_fixture: UserModel) -> None:
    """A Steam game with no matching ExternalGame record appears in not_found."""
    api_client.force_authenticate(user=user_fixture)
    with patch(
        "game_list.games.views.requests.get",
        return_value=_steam_response([{"appid": 20, "name": "Team Fortress Classic"}]),
    ):
        response = api_client.get(
            reverse("games:game-lists-steam-import"),
            {"steam_profile_id": STEAM_PROFILE_ID},
        )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matched"] == []
    assert data["not_found"] == [{"appid": 20, "name": "Team Fortress Classic"}]
    assert data["total_imported"] == 1


@pytest.mark.django_db()
def test_steam_import_cache_hit_skips_second_api_call(api_client: APIClient, user_fixture: UserModel) -> None:
    """Second request with same steam_profile_id within TTL does not call Steam API again."""
    api_client.force_authenticate(user=user_fixture)
    mock_get = MagicMock(return_value=_steam_response([]))
    with patch("game_list.games.views.requests.get", mock_get):
        api_client.get(reverse("games:game-lists-steam-import"), {"steam_profile_id": STEAM_PROFILE_ID})
        api_client.get(reverse("games:game-lists-steam-import"), {"steam_profile_id": STEAM_PROFILE_ID})
    assert mock_get.call_count == 1


@pytest.mark.django_db()
def test_steam_import_with_polish_language_matches_and_returns_polish_title(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """When Accept-Language: pl is sent, the Steam source is found and matched game titles are in Polish."""
    steam_source: ExternalGameSource = baker.make("games.ExternalGameSource", name_en="Steam")
    external_game: ExternalGame = baker.make("games.ExternalGame", external_game_source=steam_source, external_id="730")
    game: Game = baker.make("games.Game", title_en="Counter-Strike 2", title_pl="Counter-Strike 2 PL")
    game.external_games.add(external_game)

    api_client.force_authenticate(user=user_fixture)
    with patch(
        "game_list.games.views.requests.get",
        return_value=_steam_response([{"appid": 730, "name": "Counter-Strike 2"}]),
    ):
        response = api_client.get(
            reverse("games:game-lists-steam-import"),
            {"steam_profile_id": STEAM_PROFILE_ID},
            HTTP_ACCEPT_LANGUAGE="pl",
        )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["matched"]) == 1
    assert data["matched"][0]["id"] == game.id
    assert data["matched"][0]["title"] == "Counter-Strike 2 PL"
    assert data["not_found"] == []


@pytest.mark.django_db()
def test_steam_import_no_steam_source_in_db(api_client: APIClient, user_fixture: UserModel) -> None:
    """If no Steam ExternalGameSource record exists, matched is empty and no exception is raised."""
    api_client.force_authenticate(user=user_fixture)
    with patch(
        "game_list.games.views.requests.get",
        return_value=_steam_response([{"appid": 730, "name": "Counter-Strike 2"}]),
    ):
        response = api_client.get(
            reverse("games:game-lists-steam-import"),
            {"steam_profile_id": STEAM_PROFILE_ID},
        )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["matched"] == []
    assert data["not_found"] == [{"appid": 730, "name": "Counter-Strike 2"}]
    assert data["total_imported"] == 1
