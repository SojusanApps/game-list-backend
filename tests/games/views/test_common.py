"""This module contains tests for the common functionality for the viewsets in the game application."""

from typing import TYPE_CHECKING, Any
from unittest.mock import ANY

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.games.models import (
    Game,
    GameListStatus,
    GameReviewRecommendation,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()
FORBIDDEN_DETAIL = "You do not have permission to perform this action."
GAME_USER_DEPENDENT_LIST_VIEWNAMES = [
    "games:game-reviews-list",
    "games:game-lists-list",
    "games:game-follows-list",
]
GAME_USER_DEPENDENT_DETAIL_VIEWNAMES = [
    "games:game-reviews-detail",
    "games:game-lists-detail",
    "games:game-follows-detail",
]


@pytest.mark.parametrize(
    "viewname",
    [
        pytest.param(
            "games:companies-list",
            id="Check forbidden access for the creation of company.",
        ),
        pytest.param(
            "games:games-list",
            id="Check forbidden access for the creation of game.",
        ),
        pytest.param(
            "games:genres-list",
            id="Check forbidden access for the creation of genre.",
        ),
        pytest.param(
            "games:platforms-list",
            id="Check forbidden access for the creation of platform.",
        ),
        pytest.param(
            "games:game-medias-list",
            id="Check forbidden access for the creation of game media.",
        ),
        pytest.param(
            "games:game-types-list",
            id="Check forbidden access for the creation of game type.",
        ),
        pytest.param(
            "games:game-statuses-list",
            id="Check forbidden access for the creation of game status.",
        ),
        pytest.param(
            "games:game-engines-list",
            id="Check forbidden access for the creation of game engine.",
        ),
        pytest.param(
            "games:game-modes-list",
            id="Check forbidden access for the creation of game mode.",
        ),
        pytest.param(
            "games:player-perspectives-list",
            id="Check forbidden access for the creation of player perspective.",
        ),
    ],
)
@pytest.mark.django_db()
def test_forbidden_access_list(viewname: str, authenticated_api_client: APIClient) -> None:
    """Check if the unauthorized user did not have access to the protected endpoints."""
    response = authenticated_api_client.post(reverse(viewname))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": FORBIDDEN_DETAIL}


@pytest.mark.parametrize(
    "viewname",
    [
        pytest.param(
            "games:game-follows-list",
            id="Check unauthorized access for the creation of game follow.",
        ),
        pytest.param(
            "games:game-lists-list",
            id="Check unauthorized access for the creation of game list.",
        ),
        pytest.param(
            "games:game-reviews-list",
            id="Check unauthorized access for the creation of game review.",
        ),
    ],
)
@pytest.mark.django_db()
def test_unauthorized_access_list(viewname: str, api_client: APIClient) -> None:
    """Check if the unauthorized user did not have access to the protected endpoints."""
    response = api_client.post(reverse(viewname))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Authentication credentials were not provided."}


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("put", id="PUT method"),
        pytest.param("patch", id="PATCH method"),
        pytest.param("delete", id="DELETE method"),
    ],
)
@pytest.mark.parametrize(
    "viewname",
    [
        pytest.param(
            "games:companies-detail",
            id="Check forbidden access for the company with given id.",
        ),
        pytest.param(
            "games:games-detail",
            id="Check forbidden access for the game with given id.",
        ),
        pytest.param(
            "games:genres-detail",
            id="Check forbidden access for the genre with given id.",
        ),
        pytest.param(
            "games:platforms-detail",
            id="Check forbidden access for the platform with given id.",
        ),
        pytest.param(
            "games:game-medias-detail",
            id="Check forbidden access for the game media with given id.",
        ),
        pytest.param(
            "games:game-types-detail",
            id="Check forbidden access for the game type with given id.",
        ),
        pytest.param(
            "games:game-statuses-detail",
            id="Check forbidden access for the game status with given id.",
        ),
        pytest.param(
            "games:game-engines-detail",
            id="Check forbidden access for the game engine with given id.",
        ),
        pytest.param(
            "games:game-modes-detail",
            id="Check forbidden access for the game mode with given id.",
        ),
        pytest.param(
            "games:player-perspectives-detail",
            id="Check forbidden access for the player perspective with given id.",
        ),
    ],
)
@pytest.mark.django_db()
def test_forbidden_access_detail(method: str, viewname: str, authenticated_api_client: APIClient) -> None:
    """Check if the unauthorized user did not have access to the protected endpoints."""
    response = getattr(authenticated_api_client, method)(reverse(viewname, (1,)))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": FORBIDDEN_DETAIL}


@pytest.mark.parametrize(
    "viewname",
    [
        pytest.param(
            "games:game-follows-detail",
            id="Check unauthorized access for the given game follow.",
        ),
        pytest.param(
            "games:game-lists-detail",
            id="Check unauthorized access for the given game list.",
        ),
        pytest.param(
            "games:game-reviews-detail",
            id="Check unauthorized access for the given game review.",
        ),
    ],
)
@pytest.mark.django_db()
def test_unauthorized_access_detail(viewname: str, api_client: APIClient) -> None:
    """Check if the unauthorized user did not have access to the protected endpoints."""
    response = api_client.post(reverse(viewname, (1,)))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Authentication credentials were not provided."}


@pytest.mark.parametrize(
    ("viewname", "fixture_name", "expected_result"),
    [
        pytest.param(
            "games:companies-list",
            "developer_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "slug": ANY,
                        "name": ANY,
                        "company_logo_id": "",
                        "igdb_id": ANY,
                        "igdb_updated_at": ANY,
                    },
                ],
            },
            id="Test list endpoint for company.",
        ),
        pytest.param(
            "games:game-follows-list",
            "game_follow_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "game": ANY,
                        "user": ANY,
                        "created_at": "2023-06-22T16:47:12Z",
                    },
                ],
            },
            id="Test list endpoint for game follow.",
        ),
        pytest.param(
            "games:game-lists-list",
            "game_list_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "title": ANY,
                        "game_id": ANY,
                        "game_slug": ANY,
                        "game_cover_image": ANY,
                        "user": ANY,
                        "score": 5,
                        "status": GameListStatus.PLAN_TO_PLAY.label,
                        "status_code": GameListStatus.PLAN_TO_PLAY.value,
                        "description": "",
                        "completed_at": None,
                        "started_at": None,
                        "playtime": None,
                        "last_modified_at": "2023-06-22T16:47:12Z",
                        "created_at": "2023-06-22T16:47:12Z",
                        "owned_on": ANY,
                    },
                ],
            },
            id="Test list endpoint for game list.",
        ),
        pytest.param(
            "games:game-reviews-list",
            "game_review_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "recommendation_counts": None,
                "results": [
                    {
                        "id": ANY,
                        "game": ANY,
                        "user": ANY,
                        "score": None,
                        "recommendation": GameReviewRecommendation.RECOMMENDED.value,
                        "review": "test_review",
                        "created_at": "2023-06-22T16:47:12Z",
                    },
                ],
            },
            id="Test list endpoint for game review.",
        ),
        pytest.param(
            "games:games-list",
            "game_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "slug": ANY,
                        "title": ANY,
                        "release_date": None,
                        "created_at": "2023-06-22T16:47:12Z",
                        "cover_image_id": ANY,
                        "average_score": 0.0,
                        "scores_count": 0,
                        "rank_position": 0,
                        "members_count": 0,
                        "popularity": 0,
                        "game_status": ANY,
                        "game_type": ANY,
                    },
                ],
            },
            id="Test list endpoint for game.",
        ),
        pytest.param(
            "games:genres-list",
            "genre_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "name": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": ANY,
                    },
                ],
            },
            id="Test list endpoint for genre.",
        ),
        pytest.param(
            "games:platforms-list",
            "platform_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "name": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": ANY,
                        "abbreviation": "",
                    },
                ],
            },
            id="Test list endpoint for platform.",
        ),
        pytest.param(
            "games:game-medias-list",
            "game_media_fixture",
            {
                "count": 6,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "name": ANY,
                    },
                    {
                        "id": ANY,
                        "name": ANY,
                    },
                    {
                        "id": ANY,
                        "name": ANY,
                    },
                    {
                        "id": ANY,
                        "name": ANY,
                    },
                    {
                        "id": ANY,
                        "name": ANY,
                    },
                    {
                        "id": ANY,
                        "name": ANY,
                    },
                ],
            },
            id="Test list endpoint for game media.",
        ),
        pytest.param(
            "games:game-types-list",
            "game_type_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "type": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": "2023-06-22T16:47:12Z",
                    },
                ],
            },
            id="Test list endpoint for game type.",
        ),
        pytest.param(
            "games:game-statuses-list",
            "game_status_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "status": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": "2023-06-22T16:47:12Z",
                    },
                ],
            },
            id="Test list endpoint for game status.",
        ),
        pytest.param(
            "games:game-engines-list",
            "game_engine_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "name": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": "2023-06-22T16:47:12Z",
                    },
                ],
            },
            id="Test list endpoint for game engine.",
        ),
        pytest.param(
            "games:game-modes-list",
            "game_mode_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "name": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": "2023-06-22T16:47:12Z",
                    },
                ],
            },
            id="Test list endpoint for game mode.",
        ),
        pytest.param(
            "games:player-perspectives-list",
            "player_perspective_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "name": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": "2023-06-22T16:47:12Z",
                    },
                ],
            },
            id="Test list endpoint for player perspective.",
        ),
        pytest.param(
            "games:external-game-sources-list",
            "external_game_source_fixture",
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": ANY,
                        "name": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": "2023-06-22T16:47:12Z",
                    },
                ],
            },
            id="Test list endpoint for external game source.",
        ),
    ],
)
@pytest.mark.django_db()
def test_list_model(
    request: pytest.FixtureRequest,
    viewname: str,
    fixture_name: str,
    expected_result: Mapping[str, Any],
    authenticated_api_client: APIClient,
) -> None:
    """Get the list of objects for the given model."""
    request.getfixturevalue(fixture_name)
    response = authenticated_api_client.get(reverse(viewname))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == expected_result


@pytest.mark.parametrize(
    ("viewname", "fixture_name", "expected_result"),
    [
        pytest.param(
            "games:companies-detail",
            "developer_fixture",
            {
                "id": ANY,
                "slug": ANY,
                "name": ANY,
                "company_logo_id": "",
                "igdb_id": ANY,
                "igdb_updated_at": ANY,
                "games_developed": [],
                "games_published": [],
            },
            id="Get the company by id.",
        ),
        pytest.param(
            "games:game-follows-detail",
            "game_follow_fixture",
            {
                "id": ANY,
                "game": ANY,
                "user": ANY,
                "created_at": "2023-06-22T16:47:12Z",
            },
            id="Get the game follow by id.",
        ),
        pytest.param(
            "games:game-lists-detail",
            "game_list_fixture",
            {
                "id": ANY,
                "title": ANY,
                "game_id": ANY,
                "game_slug": ANY,
                "game_cover_image": ANY,
                "user": ANY,
                "score": 5,
                "status": GameListStatus.PLAN_TO_PLAY.label,
                "status_code": GameListStatus.PLAN_TO_PLAY.value,
                "description": "",
                "completed_at": None,
                "started_at": None,
                "playtime": None,
                "last_modified_at": "2023-06-22T16:47:12Z",
                "created_at": "2023-06-22T16:47:12Z",
                "owned_on": ANY,
            },
            id="Get the game list by id.",
        ),
        pytest.param(
            "games:game-reviews-detail",
            "game_review_fixture",
            {
                "id": ANY,
                "game": ANY,
                "user": ANY,
                "review": "test_review",
                "score": None,
                "recommendation": GameReviewRecommendation.RECOMMENDED.value,
                "created_at": "2023-06-22T16:47:12Z",
            },
            id="Get the game review by id.",
        ),
        pytest.param(
            "games:games-detail",
            "game_fixture",
            {
                "cover_image_id": ANY,
                "created_at": "2023-06-22T16:47:12Z",
                "summary": "",
                "igdb_id": ANY,
                "igdb_updated_at": ANY,
                "developer": {
                    "id": ANY,
                    "slug": ANY,
                    "name": ANY,
                    "company_logo_id": "",
                    "igdb_id": ANY,
                    "igdb_updated_at": ANY,
                },
                "genres": [{"id": ANY, "name": ANY, "igdb_id": ANY, "igdb_updated_at": ANY}],
                "id": ANY,
                "slug": ANY,
                "last_modified_at": "2023-06-22T16:47:12Z",
                "platforms": [{"id": ANY, "name": ANY, "igdb_id": ANY, "abbreviation": "", "igdb_updated_at": ANY}],
                "publisher": {
                    "id": ANY,
                    "slug": ANY,
                    "name": ANY,
                    "company_logo_id": "",
                    "igdb_id": ANY,
                    "igdb_updated_at": ANY,
                },
                "external_games": [
                    {
                        "id": ANY,
                        "external_game_source": ANY,
                        "igdb_id": ANY,
                        "igdb_updated_at": ANY,
                        "url": ANY,
                        "external_id": ANY,
                    },
                ],
                "release_date": None,
                "title": ANY,
                "title_en": ANY,
                "average_score": 0.0,
                "members_count": 0,
                "popularity": 0,
                "rank_position": 0,
                "scores_count": 0,
                "game_type": {"id": ANY, "type": ANY, "igdb_id": ANY, "igdb_updated_at": ANY},
                "game_status": {"id": ANY, "status": ANY, "igdb_id": ANY, "igdb_updated_at": ANY},
                "parent_game": None,
                "bundles": [],
                "dlcs": [],
                "expanded_games": [],
                "expansions": [],
                "forks": [],
                "ports": [],
                "standalone_expansions": [],
                "game_engines": [{"id": ANY, "name": ANY, "igdb_id": ANY, "igdb_updated_at": ANY}],
                "game_modes": [{"id": ANY, "name": ANY, "igdb_id": ANY, "igdb_updated_at": ANY}],
                "player_perspectives": [{"id": ANY, "name": ANY, "igdb_id": ANY, "igdb_updated_at": ANY}],
                "screenshots": [],
            },
            id="Get the game by id.",
        ),
        pytest.param(
            "games:genres-detail",
            "genre_fixture",
            {
                "id": ANY,
                "name": ANY,
                "igdb_id": ANY,
                "igdb_updated_at": ANY,
            },
            id="Get the genre by id.",
        ),
        pytest.param(
            "games:platforms-detail",
            "platform_fixture",
            {
                "id": ANY,
                "name": ANY,
                "igdb_id": ANY,
                "igdb_updated_at": ANY,
                "abbreviation": "",
            },
            id="Get the platform by id.",
        ),
        pytest.param(
            "games:game-medias-detail",
            "game_media_fixture",
            {
                "id": ANY,
                "name": ANY,
            },
            id="Get the game media by id.",
        ),
        pytest.param(
            "games:game-types-detail",
            "game_type_fixture",
            {
                "id": ANY,
                "type": ANY,
                "igdb_id": ANY,
                "igdb_updated_at": "2023-06-22T16:47:12Z",
            },
            id="Get the game type by id.",
        ),
        pytest.param(
            "games:game-statuses-detail",
            "game_status_fixture",
            {
                "id": ANY,
                "status": ANY,
                "igdb_id": ANY,
                "igdb_updated_at": "2023-06-22T16:47:12Z",
            },
            id="Get the game status by id.",
        ),
        pytest.param(
            "games:game-engines-detail",
            "game_engine_fixture",
            {
                "id": ANY,
                "name": ANY,
                "igdb_id": ANY,
                "igdb_updated_at": "2023-06-22T16:47:12Z",
            },
            id="Get the game engine by id.",
        ),
        pytest.param(
            "games:game-modes-detail",
            "game_mode_fixture",
            {
                "id": ANY,
                "name": ANY,
                "igdb_id": ANY,
                "igdb_updated_at": "2023-06-22T16:47:12Z",
            },
            id="Get the game mode by id.",
        ),
        pytest.param(
            "games:player-perspectives-detail",
            "player_perspective_fixture",
            {
                "id": ANY,
                "name": ANY,
                "igdb_id": ANY,
                "igdb_updated_at": "2023-06-22T16:47:12Z",
            },
            id="Get the player perspective by id.",
        ),
        pytest.param(
            "games:external-game-sources-detail",
            "external_game_source_fixture",
            {
                "id": ANY,
                "name": ANY,
                "igdb_id": ANY,
                "igdb_updated_at": "2023-06-22T16:47:12Z",
            },
            id="Get the external game source by id.",
        ),
    ],
)
@pytest.mark.django_db()
def test_get_model_detail(
    request: pytest.FixtureRequest,
    viewname: str,
    fixture_name: str,
    expected_result: Mapping[str, Any],
    authenticated_api_client: APIClient,
) -> None:
    """Check that the user can get the model instance data with the given id."""
    model_instance = request.getfixturevalue(fixture_name)
    response = authenticated_api_client.get(reverse(viewname, (model_instance.pk,)))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == expected_result


@freeze_time("2023-06-22 22:20:01")
@pytest.mark.parametrize(
    ("viewname", "initial_data", "expected_result"),
    [
        pytest.param(
            "games:game-follows-list",
            {},
            {
                "id": ANY,
                "created_at": "2023-06-22T22:20:01Z",
            },
            id="Create a new game follow.",
        ),
        pytest.param(
            "games:game-lists-list",
            {
                "status": GameListStatus.PLAN_TO_PLAY.value,
                "score": 1,
            },
            {
                "id": ANY,
                "score": 1,
                "status": GameListStatus.PLAN_TO_PLAY.value,
                "description": "",
                "completed_at": None,
                "started_at": None,
                "playtime": None,
                "created_at": "2023-06-22T22:20:01Z",
                "last_modified_at": "2023-06-22T22:20:01Z",
                "owned_on": ANY,
            },
            id="Create a new game list.",
        ),
        pytest.param(
            "games:game-reviews-list",
            {
                "review": "test review - new",
                "recommendation": GameReviewRecommendation.RECOMMENDED.value,
            },
            {
                "id": ANY,
                "created_at": "2023-06-22T22:20:01Z",
            },
            id="Create a new game review.",
        ),
        pytest.param(
            "games:game-medias-list",
            {
                "name": "created_media",
            },
            {
                "id": ANY,
            },
            id="Creation of the game media.",
        ),
    ],
)
@pytest.mark.django_db()
def test_create_model(
    viewname: str,  # NOSONAR
    initial_data: dict[str, Any],
    expected_result: dict[str, Any],
    admin_user_fixture: UserModel,
    game_fixture: Game,
    admin_authenticated_api_client: APIClient,
) -> None:
    """Check if creation of the new dictionary model is working properly."""
    if viewname in GAME_USER_DEPENDENT_LIST_VIEWNAMES:
        initial_data |= {"user": admin_user_fixture.pk, "game": game_fixture.pk}
    response = admin_authenticated_api_client.post(reverse(viewname), initial_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == initial_data | expected_result


@freeze_time("2023-06-22 22:20:01")
@pytest.mark.parametrize(
    "method",
    [
        pytest.param(
            "put",
            id="PUT update test.",
        ),
        pytest.param(
            "patch",
            id="PATCH update test.",
        ),
    ],
)
@pytest.mark.parametrize(
    ("viewname", "fixture_name", "update_data", "expected_result"),
    [
        pytest.param(
            "games:game-follows-detail",
            "game_follow_fixture",
            {},
            {
                "created_at": "2023-06-22T16:47:12Z",
            },
            id="Update a game follow.",
        ),
        pytest.param(
            "games:game-lists-detail",
            "game_list_fixture",
            {
                "score": 10,
                "status": GameListStatus.COMPLETED.value,
            },
            {
                "score": 10,
                "status": GameListStatus.COMPLETED.value,
                "description": "",
                "completed_at": None,
                "started_at": None,
                "playtime": None,
                "created_at": "2023-06-22T16:47:12Z",
                "last_modified_at": "2023-06-22T22:20:01Z",
                "owned_on": ANY,
            },
            id="Update a game list.",
        ),
        pytest.param(
            "games:game-reviews-detail",
            "game_review_fixture",
            {
                "review": "Updated review.",
                "recommendation": GameReviewRecommendation.NOT_RECOMMENDED.value,
            },
            {
                "created_at": "2023-06-22T16:47:12Z",
            },
            id="Update a game review.",
        ),
    ],
)
@pytest.mark.django_db()
def test_update_model(
    request: pytest.FixtureRequest,
    method: str,
    viewname: str,
    fixture_name: str,
    update_data: dict[str, Any],
    expected_result: dict[str, Any],
    admin_authenticated_api_client: APIClient,
) -> None:
    """Check if updates method works properly for game models."""
    if viewname in GAME_USER_DEPENDENT_DETAIL_VIEWNAMES:
        update_data |= {
            "user": baker.make(User).pk,
            "game": baker.make(Game).pk,
        }
    model_instance = request.getfixturevalue(fixture_name)
    response = getattr(admin_authenticated_api_client, method)(
        reverse(viewname, (model_instance.pk,)),
        update_data,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == update_data | expected_result | {"id": model_instance.pk}


@pytest.mark.parametrize(
    ("viewname", "fixture_name", "total_count_after_deletion"),
    [
        pytest.param(
            "games:game-follows-detail",
            "game_follow_fixture",
            0,
            id="Delete the game follow.",
        ),
        pytest.param(
            "games:game-lists-detail",
            "game_list_fixture",
            0,
            id="Delete the game list.",
        ),
        pytest.param(
            "games:game-reviews-detail",
            "game_review_fixture",
            0,
            id="Delete the game review.",
        ),
        pytest.param(
            "games:game-medias-detail",
            "game_media_fixture",
            5,
            id="Delete the game media.",
        ),
    ],
)
@pytest.mark.django_db()
def test_delete_model(
    request: pytest.FixtureRequest,
    viewname: str,
    fixture_name: str,
    total_count_after_deletion: int,
    admin_authenticated_api_client: APIClient,
) -> None:
    """Check if deletion of the game model works properly."""
    model_instance = request.getfixturevalue(fixture_name)
    response = admin_authenticated_api_client.delete(reverse(viewname, (model_instance.pk,)))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert model_instance.__class__.objects.count() == total_count_after_deletion
