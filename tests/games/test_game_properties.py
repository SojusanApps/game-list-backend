"""Tests for game properties."""

import pytest
from model_bakery import baker

from game_list.games.models import Game, GameList
from game_list.games.tasks import recalculate_ranks


@pytest.mark.django_db()
def test_game_average_score() -> None:
    """Test that the average score is correctly updated."""
    game = baker.make(Game)
    # create game lists with scores
    baker.make(GameList, game=game, score=10)
    baker.make(GameList, game=game, score=5)

    # Refresh to get updated stats
    game.refresh_from_db()
    # 15 / 2 = 7.5
    assert game.average_score == 7.50  # noqa: PLR2004


@pytest.mark.django_db()
def test_game_rank_position() -> None:
    """Test that the rank position is correctly recalculated."""
    game1 = baker.make(Game)  # score 10
    game2 = baker.make(Game)  # score 8
    game3 = baker.make(Game)  # score 5

    baker.make(GameList, game=game1, score=10)
    baker.make(GameList, game=game2, score=8)
    baker.make(GameList, game=game3, score=5)

    recalculate_ranks()

    game1.refresh_from_db()
    game2.refresh_from_db()
    game3.refresh_from_db()

    assert game1.rank_position == 1
    assert game2.rank_position == 2  # noqa: PLR2004
    assert game3.rank_position == 3  # noqa: PLR2004


@pytest.mark.django_db()
def test_game_popularity() -> None:
    """Test that the popularity is correctly recalculated."""
    game1 = baker.make(Game)  # 3 members
    game2 = baker.make(Game)  # 2 members
    game3 = baker.make(Game)  # 1 member

    baker.make(GameList, game=game1, _quantity=3)
    baker.make(GameList, game=game2, _quantity=2)
    baker.make(GameList, game=game3, _quantity=1)

    recalculate_ranks()

    game1.refresh_from_db()
    game2.refresh_from_db()
    game3.refresh_from_db()

    assert game1.popularity == 1
    assert game2.popularity == 2  # noqa: PLR2004
    assert game3.popularity == 3  # noqa: PLR2004
