"""Tests for the `recalculate_stats` management command."""

from decimal import Decimal

import pytest
from django.core.management import call_command
from model_bakery import baker

from my_game_list.games.models import Game, GameList, GameListStatus, GameStats


@pytest.mark.django_db()
def test_recalculate_stats_creates_missing_gamestats() -> None:
    """A game whose GameStats row was deleted gets a fresh, zeroed GameStats row created."""
    game = baker.make(Game)
    GameStats.objects.filter(game=game).delete()
    assert not GameStats.objects.filter(game=game).exists()

    call_command("recalculate_stats")

    stats = GameStats.objects.get(game=game)
    assert stats.score_sum == 0
    assert stats.score_count == 0
    assert stats.average_score == 0
    assert stats.members_count == 0


@pytest.mark.django_db()
def test_recalculate_stats_computes_aggregate_math_from_gamelist_scores() -> None:
    """The command recomputes score_sum/score_count/average_score/members_count from GameList rows."""
    game = baker.make(Game)
    baker.make(GameList, game=game, score=10, status=GameListStatus.COMPLETED, _quantity=1)
    baker.make(GameList, game=game, score=8, status=GameListStatus.COMPLETED, _quantity=1)
    baker.make(GameList, game=game, score=6, status=GameListStatus.PLAYING, _quantity=1)
    # Corrupt the stats that the GameList signals already computed, to prove the command
    # genuinely recomputes them rather than relying on the values being right already.
    GameStats.objects.filter(game=game).update(score_sum=0, score_count=0, average_score=0, members_count=0)

    call_command("recalculate_stats")

    stats = GameStats.objects.get(game=game)
    assert stats.score_sum == 24  # noqa: PLR2004
    assert stats.score_count == 3  # noqa: PLR2004
    assert stats.average_score == Decimal("8.00")
    assert stats.members_count == 3  # noqa: PLR2004


@pytest.mark.django_db()
def test_recalculate_stats_resets_to_zero_when_no_gamelist_entries() -> None:
    """A game with stale nonzero GameStats but no GameList entries gets reset to zero."""
    game = baker.make(Game)
    GameStats.objects.filter(game=game).update(
        score_sum=50,
        score_count=5,
        average_score=Decimal("10.00"),
        members_count=5,
    )

    call_command("recalculate_stats")

    stats = GameStats.objects.get(game=game)
    assert stats.score_sum == 0
    assert stats.score_count == 0
    assert stats.average_score == 0
    assert stats.members_count == 0


@pytest.mark.django_db()
def test_recalculate_stats_also_recalculates_ranks() -> None:
    """After recomputing aggregates, the command also assigns rank_position and popularity."""
    game = baker.make(Game)
    baker.make(GameList, game=game, score=10, status=GameListStatus.COMPLETED)

    call_command("recalculate_stats")

    stats = GameStats.objects.get(game=game)
    assert stats.rank_position == 1
    assert stats.popularity == 1
