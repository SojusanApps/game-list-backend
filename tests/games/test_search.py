"""Tests for the games app fuzzy title search helpers."""

from game_list.games.models import Game
from game_list.games.search import ranked_title_match_pks, score_title_match


def test_score_title_match_returns_zero_for_empty_query() -> None:
    """An empty normalized query scores 0.0 against any title."""
    assert score_title_match("", "half life") == 0.0


def test_score_title_match_returns_zero_for_empty_title() -> None:
    """An empty normalized title scores 0.0 against any query."""
    assert score_title_match("half life", "") == 0.0


def test_ranked_title_match_pks_returns_empty_list_for_blank_value() -> None:
    """A value that normalizes to an empty string short-circuits before touching the queryset."""
    assert ranked_title_match_pks(Game.objects.all(), "   ") == []
