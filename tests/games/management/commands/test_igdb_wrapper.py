"""Tests for the IGDB API wrapper (``_igdb_wrapper``), mocking all HTTP interaction."""

from __future__ import annotations

import types
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.conf import settings

from game_list.games.management.commands._igdb_wrapper import (
    IGDBCompanyResponse,
    IGDBEndpoints,
    IGDBExternalGameResponse,
    IGDBExternalGameSourceResponse,
    IGDBGameEngineResponse,
    IGDBGameModeResponse,
    IGDBGameResponse,
    IGDBGameStatusResponse,
    IGDBGameTypeResponse,
    IGDBGenreResponse,
    IGDBImageResponse,
    IGDBInteractionError,
    IGDBInvolvedCompanyResponse,
    IGDBPlatformResponse,
    IGDBPlayerPerspectiveResponse,
    IGDBWrapper,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any

MODULE = "game_list.games.management.commands._igdb_wrapper"
TEST_ACCESS_TOKEN = "test-access-token"  # noqa: S105 (test fixture value, not a real secret)


def _auth_response(access_token: str = TEST_ACCESS_TOKEN) -> MagicMock:
    """Build a mock ``requests.Response`` for a successful IGDB token request."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": access_token,
        "expires_in": 3600,
        "token_type": "bearer",
    }
    return mock_response


def _json_response(json_data: list[dict[str, Any]]) -> MagicMock:
    """Build a mock ``requests.Response`` whose ``.json()`` returns the given payload."""
    mock_response = MagicMock()
    mock_response.json.return_value = json_data
    return mock_response


def _error_response() -> MagicMock:
    """Build a mock ``requests.Response`` whose ``raise_for_status`` raises ``HTTPError``."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("boom")
    return mock_response


def _genre_payload(count: int, start: int = 0) -> list[dict[str, Any]]:
    """Build a list of raw IGDB genre dicts."""
    return [{"id": start + i, "updated_at": 0, "name": f"Genre {start + i}"} for i in range(count)]


@pytest.fixture
def wrapper() -> Iterator[IGDBWrapper]:
    """An ``IGDBWrapper`` built with a mocked, successful token fetch."""
    with patch(f"{MODULE}.requests.post", return_value=_auth_response()):
        yield IGDBWrapper()


def test_init_fetches_access_token_and_builds_headers() -> None:
    """The constructor fetches an access token and stores it in the auth headers."""
    with patch(
        f"{MODULE}.requests.post",
        return_value=_auth_response(access_token="fresh-token"),  # noqa: S106 (test fixture value, not a real secret)
    ) as mock_post:
        instance = IGDBWrapper()

    mock_post.assert_called_once_with(IGDBWrapper.IGDB_AUTHENTICATION_URL, timeout=10)
    assert instance.basic_auth_headers == {
        "Client-ID": settings.IGDB_CLIENT_ID,
        "Authorization": "Bearer fresh-token",
    }


def test_get_igdb_access_token_raises_igdb_interaction_error_on_http_error() -> None:
    """A non-2xx response from the token endpoint is translated into an ``IGDBInteractionError``."""
    with (
        patch(f"{MODULE}.requests.post", return_value=_error_response()),
        pytest.raises(IGDBInteractionError, match="Unable to get the access_token for IGDB"),
    ):
        IGDBWrapper()


class TestApiRequest:
    """Tests for ``IGDBWrapper.api_request``."""

    def test_raises_when_query_is_empty(self, wrapper: IGDBWrapper) -> None:
        """An empty query string is rejected before any HTTP call is made."""
        with (
            patch(f"{MODULE}.requests.post") as mock_post,
            pytest.raises(IGDBInteractionError, match="No query provided"),
        ):
            wrapper.api_request(IGDBEndpoints.GENRES, "")

        mock_post.assert_not_called()

    def test_builds_request_and_casts_response(self, wrapper: IGDBWrapper) -> None:
        """The request is built with the right URL/headers/body and the response is cast to dataclasses."""
        payload = [{"id": 1, "updated_at": 0, "name": "RPG"}]
        with patch(f"{MODULE}.requests.post", return_value=_json_response(payload)) as mock_post:
            result = wrapper.api_request(IGDBEndpoints.GENRES, "fields name; limit 10;")

        mock_post.assert_called_once_with(
            f"{IGDBWrapper.IGDB_BASE_URL}genres",
            data="fields name; limit 10;",
            headers=wrapper.basic_auth_headers,
            timeout=10,
        )
        assert result == [IGDBGenreResponse(id=1, updated_at=0, name="RPG")]

    def test_raises_igdb_interaction_error_on_http_error(self, wrapper: IGDBWrapper) -> None:
        """A non-2xx response from the IGDB API is translated into an ``IGDBInteractionError``."""
        with (
            patch(f"{MODULE}.requests.post", return_value=_error_response()),
            pytest.raises(IGDBInteractionError, match="Unable to get the genres"),
        ):
            wrapper.api_request(IGDBEndpoints.GENRES, "fields name;")

    @pytest.mark.parametrize(
        ("endpoint", "payload", "expected_type"),
        [
            pytest.param(
                IGDBEndpoints.PLATFORMS,
                {"id": 1, "updated_at": 0, "name": "PC", "abbreviation": "PC"},
                IGDBPlatformResponse,
                id="platforms",
            ),
            pytest.param(
                IGDBEndpoints.GENRES,
                {"id": 1, "updated_at": 0, "name": "RPG"},
                IGDBGenreResponse,
                id="genres",
            ),
            pytest.param(
                IGDBEndpoints.COMPANIES,
                {"id": 1, "updated_at": 0, "name": "Nintendo", "slug": "nintendo"},
                IGDBCompanyResponse,
                id="companies",
            ),
            pytest.param(
                IGDBEndpoints.GAMES,
                {"id": 1, "updated_at": 0, "name": "Some Game", "slug": "some-game"},
                IGDBGameResponse,
                id="games",
            ),
            pytest.param(
                IGDBEndpoints.GAME_MODES,
                {"id": 1, "updated_at": 0, "name": "Single player"},
                IGDBGameModeResponse,
                id="game_modes",
            ),
            pytest.param(
                IGDBEndpoints.PLAYER_PERSPECTIVES,
                {"id": 1, "updated_at": 0, "name": "First person"},
                IGDBPlayerPerspectiveResponse,
                id="player_perspectives",
            ),
            pytest.param(
                IGDBEndpoints.GAME_ENGINES,
                {"id": 1, "updated_at": 0, "name": "Unreal Engine"},
                IGDBGameEngineResponse,
                id="game_engines",
            ),
            pytest.param(
                IGDBEndpoints.GAME_TYPES,
                {"id": 1, "updated_at": 0, "type": "Main game"},
                IGDBGameTypeResponse,
                id="game_types",
            ),
            pytest.param(
                IGDBEndpoints.GAME_STATUSES,
                {"id": 1, "updated_at": 0, "status": "Released"},
                IGDBGameStatusResponse,
                id="game_statuses",
            ),
            pytest.param(
                IGDBEndpoints.EXTERNAL_GAMES,
                {"id": 1, "updated_at": 0, "uid": "123", "external_game_source": 1},
                IGDBExternalGameResponse,
                id="external_games",
            ),
            pytest.param(
                IGDBEndpoints.EXTERNAL_GAME_SOURCES,
                {"id": 1, "updated_at": 0, "name": "Steam"},
                IGDBExternalGameSourceResponse,
                id="external_game_sources",
            ),
        ],
    )
    def test_casts_each_endpoint_to_its_dataclass(
        self,
        wrapper: IGDBWrapper,
        endpoint: IGDBEndpoints,
        payload: dict[str, Any],
        expected_type: type,
    ) -> None:
        """Every ``IGDBEndpoints`` member is mapped to its matching response dataclass."""
        with patch(f"{MODULE}.requests.post", return_value=_json_response([payload])):
            result = wrapper.api_request(endpoint, "fields *;")

        assert len(result) == 1
        assert isinstance(result[0], expected_type)
        assert result[0].id == payload["id"]

    def test_unknown_endpoint_raises_igdb_interaction_error(self, wrapper: IGDBWrapper) -> None:
        """``_cast_response`` raises for an endpoint that has no matching dataclass in the response map."""
        fake_endpoint = types.SimpleNamespace(value="unknown_endpoint")

        # Only reachable via the private API, with a fake enum-like object standing in for IGDBEndpoints.
        with pytest.raises(IGDBInteractionError, match="Unknown endpoint: unknown_endpoint"):
            wrapper._cast_response(fake_endpoint, [{"id": 1}])  # type: ignore[arg-type]  # noqa: SLF001


class TestApiMultiRequest:
    """Tests for ``IGDBWrapper.api_multi_request``."""

    def test_raises_when_query_is_empty(self, wrapper: IGDBWrapper) -> None:
        """An empty query string is rejected before any session is created."""
        with pytest.raises(IGDBInteractionError, match="No query provided"):
            wrapper.api_multi_request(IGDBEndpoints.GENRES, "")

    def test_issues_one_request_per_page_with_increasing_offsets(self, wrapper: IGDBWrapper) -> None:
        """Up to ``MAX_REQUESTS_TO_IGDB`` parallel requests are issued, each with its own offset."""
        responses = [_json_response(_genre_payload(1, start=i)) for i in range(IGDBWrapper.MAX_REQUESTS_TO_IGDB)]
        futures = []
        for response in responses:
            future = MagicMock()
            future.result.return_value = response
            futures.append(future)

        with patch(f"{MODULE}.FuturesSession") as mock_session_cls:
            mock_session = mock_session_cls.return_value
            mock_session.post.side_effect = futures

            result = wrapper.api_multi_request(IGDBEndpoints.GENRES, "fields name;", offset=0)

        mock_session_cls.assert_called_once_with(max_workers=IGDBWrapper.MAX_REQUESTS_TO_IGDB)
        assert result == responses
        called_data = [call.kwargs["data"] for call in mock_session.post.call_args_list]
        assert called_data == [
            "fields name;offset 0;sort id;",
            "fields name;offset 500;sort id;",
            "fields name;offset 1000;sort id;",
            "fields name;offset 1500;sort id;",
        ]
        called_urls = [call.kwargs["url"] for call in mock_session.post.call_args_list]
        assert all(url == f"{IGDBWrapper.IGDB_BASE_URL}genres" for url in called_urls)


class TestIterAllObjects:
    """Tests for ``IGDBWrapper.iter_all_objects``."""

    def test_stops_after_a_single_partial_page(
        self,
        wrapper: IGDBWrapper,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A batch smaller than a full page ends the loop after a single yield."""
        page_limit = IGDBWrapper.MAX_REQUESTS_TO_IGDB * IGDBWrapper.QUERY_ITEM_LIMIT
        small_batch = [_json_response(_genre_payload(2))]
        mock_multi_request = MagicMock(return_value=small_batch)
        monkeypatch.setattr(wrapper, "api_multi_request", mock_multi_request)

        batches = list(wrapper.iter_all_objects(IGDBEndpoints.GENRES, "fields name;"))

        assert len(batches) == 1
        assert batches[0] == [
            IGDBGenreResponse(id=0, updated_at=0, name="Genre 0"),
            IGDBGenreResponse(id=1, updated_at=0, name="Genre 1"),
        ]
        mock_multi_request.assert_called_once_with(IGDBEndpoints.GENRES, "fields name;limit 500;", 0)
        assert page_limit == IGDBWrapper.MAX_REQUESTS_TO_IGDB * IGDBWrapper.QUERY_ITEM_LIMIT

    def test_continues_to_next_offset_when_a_page_is_full(
        self,
        wrapper: IGDBWrapper,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A full page (MAX_REQUESTS_TO_IGDB * QUERY_ITEM_LIMIT items) triggers another round at the next offset."""
        partial_page_size = 3
        full_page = [_json_response(_genre_payload(IGDBWrapper.QUERY_ITEM_LIMIT))] * IGDBWrapper.MAX_REQUESTS_TO_IGDB
        partial_page = [_json_response(_genre_payload(partial_page_size, start=9000))]
        mock_multi_request = MagicMock(side_effect=[full_page, partial_page])
        monkeypatch.setattr(wrapper, "api_multi_request", mock_multi_request)
        monkeypatch.setattr(f"{MODULE}.time.sleep", MagicMock())

        batches = list(wrapper.iter_all_objects(IGDBEndpoints.GENRES, "fields name;"))

        expected_offset = IGDBWrapper.MAX_REQUESTS_TO_IGDB * IGDBWrapper.QUERY_ITEM_LIMIT
        assert len(batches) == 2  # noqa: PLR2004
        assert len(batches[0]) == expected_offset
        assert len(batches[1]) == partial_page_size
        assert mock_multi_request.call_args_list[0].args == (IGDBEndpoints.GENRES, "fields name;limit 500;", 0)
        assert mock_multi_request.call_args_list[1].args == (
            IGDBEndpoints.GENRES,
            "fields name;limit 500;",
            expected_offset,
        )


class TestDataclassPostInit:
    """Tests for the ``__post_init__`` validation/casting logic on the response dataclasses."""

    def test_company_response_casts_dict_logo_to_image_response(self) -> None:
        """A raw ``logo`` dict is converted into an ``IGDBImageResponse`` instance."""
        company = IGDBCompanyResponse(
            id=1,
            updated_at=0,
            name="Nintendo",
            slug="nintendo",
            logo={"id": 2, "image_id": "abc123"},  # type: ignore[arg-type]
        )

        assert company.logo == IGDBImageResponse(id=2, image_id="abc123")

    def test_company_response_leaves_missing_logo_as_none(self) -> None:
        """No ``logo`` provided leaves the field as ``None`` rather than raising."""
        company = IGDBCompanyResponse(id=1, updated_at=0, name="Nintendo", slug="nintendo")

        assert company.logo is None

    def test_game_response_casts_cover_involved_companies_and_screenshots(self) -> None:
        """Raw ``cover``, ``involved_companies`` and ``screenshots`` dicts are cast to their dataclasses."""
        game = IGDBGameResponse(
            id=1,
            updated_at=0,
            name="Some Game",
            slug="some-game",
            cover={"id": 10, "image_id": "cover-image"},  # type: ignore[arg-type]
            involved_companies=[
                {"id": 20, "company": 5, "developer": True, "publisher": False},  # type: ignore[list-item]
            ],
            screenshots=[
                {"id": 30, "image_id": "shot-1"},  # type: ignore[list-item]
                {"id": 31, "image_id": "shot-2"},  # type: ignore[list-item]
            ],
        )

        assert game.cover == IGDBImageResponse(id=10, image_id="cover-image")
        assert game.involved_companies == [
            IGDBInvolvedCompanyResponse(id=20, company=5, developer=True, publisher=False),
        ]
        assert game.screenshots == [
            IGDBImageResponse(id=30, image_id="shot-1"),
            IGDBImageResponse(id=31, image_id="shot-2"),
        ]

    def test_game_response_leaves_optional_fields_as_none_when_absent(self) -> None:
        """No ``cover``/``involved_companies``/``screenshots`` provided leaves those fields as ``None``."""
        game = IGDBGameResponse(id=1, updated_at=0, name="Some Game", slug="some-game")

        assert game.cover is None
        assert game.involved_companies is None
        assert game.screenshots is None
