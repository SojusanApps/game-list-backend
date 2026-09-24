"""The fixtures used within games test module."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from model_bakery import baker

from game_list.games.models import (
    Company,
    ExternalGame,
    ExternalGameSource,
    Game,
    GameEngine,
    GameFollow,
    GameList,
    GameListStatus,
    GameMedia,
    GameMode,
    GameReview,
    GameStatus,
    GameType,
    Genre,
    Platform,
    PlayerPerspective,
)

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def other_user_fixture() -> UserModel:
    """A fixture with a second user, distinct from user_fixture."""
    return baker.make(User, username="other_user", email="other_user@email.com", password="test")  # noqa: S106


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def game_type_fixture() -> GameType:
    """A fixture with a test game type."""
    return baker.make("games.GameType")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def game_status_fixture() -> GameStatus:
    """A fixture with a test game status."""
    return baker.make("games.GameStatus")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def game_engine_fixture() -> GameEngine:
    """A fixture with a test game engine."""
    return baker.make("games.GameEngine")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def game_mode_fixture() -> GameMode:
    """A fixture with a test game mode."""
    return baker.make("games.GameMode")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def player_perspective_fixture() -> PlayerPerspective:
    """A fixture with a test player perspective."""
    return baker.make("games.PlayerPerspective")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def external_game_source_fixture() -> ExternalGameSource:
    """A fixture with a test external game source."""
    return baker.make("games.ExternalGameSource")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def external_game_fixture(external_game_source_fixture: ExternalGameSource) -> ExternalGame:
    """A fixture with a test external game."""
    return baker.make("games.ExternalGame", external_game_source=external_game_source_fixture)


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def developer_fixture() -> Company:
    """A fixture with a test developer."""
    return baker.make("games.Company")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def platform_fixture() -> Platform:
    """A fixture with a test platform."""
    return baker.make("games.Platform")


@pytest.fixture
def game_media_fixture() -> GameMedia:
    """A fixture with a test game media."""
    return baker.make("games.GameMedia")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def publisher_fixture() -> Company:
    """A fixture with a test publisher."""
    return baker.make("games.Company")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def genre_fixture() -> Genre:
    """A fixture with a test genre."""
    return baker.make("games.Genre")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def game_fixture(
    developer_fixture: Company,
    platform_fixture: Platform,
    publisher_fixture: Company,
    genre_fixture: Genre,
    game_type_fixture: GameType,
    game_status_fixture: GameStatus,
    game_engine_fixture: GameEngine,
    game_mode_fixture: GameMode,
    player_perspective_fixture: PlayerPerspective,
    external_game_fixture: ExternalGame,
) -> Game:
    """A fixture with a test game."""
    game: Game = baker.make(
        "games.Game",
        developer=developer_fixture,
        publisher=publisher_fixture,
        game_type=game_type_fixture,
        game_status=game_status_fixture,
    )
    game.genres.add(genre_fixture)
    game.platforms.add(platform_fixture)
    game.game_engines.add(game_engine_fixture)
    game.game_modes.add(game_mode_fixture)
    game.player_perspectives.add(player_perspective_fixture)
    game.external_games.add(external_game_fixture)
    return game


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def game_review_fixture(user_fixture: UserModel, game_fixture: Game) -> GameReview:
    """A fixture with a test game review."""
    return GameReview.objects.create(
        review="test_review",
        recommendation=GameReview.Recommendation.RECOMMENDED,
        language=GameReview.Language.ENGLISH,
        game=game_fixture,
        user=user_fixture,
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def game_list_fixture(user_fixture: UserModel, game_fixture: Game) -> GameList:
    """A fixture with a test game list."""
    return GameList.objects.create(
        score=5,
        status=GameListStatus.PLAN_TO_PLAY,
        game=game_fixture,
        user=user_fixture,
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def game_follow_fixture(user_fixture: UserModel, game_fixture: Game) -> GameFollow:
    """A fixture with a test game follow."""
    return GameFollow.objects.create(game=game_fixture, user=user_fixture)
