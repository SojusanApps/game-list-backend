"""Tests for the games app querysets."""

import pytest
from model_bakery import baker

from my_game_list.games.models import Game


@pytest.mark.django_db()
def test_with_stats_select_related_returns_the_game_with_its_stats() -> None:
    """with_stats() select_related's the stats relation without changing which row is returned."""
    game = baker.make(Game)

    result = Game.objects.with_stats().get(pk=game.pk)

    assert result.pk == game.pk
    assert result.stats.pk == game.stats.pk
