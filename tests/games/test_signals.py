"""Tests for games signals."""

import pytest
from django_prometheus.testutils import assert_metric_diff, save_registry
from model_bakery import baker

from game_list.games.models import GameList, GameListStatus


@pytest.mark.django_db()
def test_creating_game_list_entry_increments_game_lists_entries_created_total(
    game_list_fixture: GameList,
) -> None:
    """Creating a GameList entry increments game_lists_entries_created_total by 1."""
    registry = save_registry()
    baker.make(GameList, game=game_list_fixture.game, user=baker.make("users.User"), status=GameListStatus.PLAYING)
    assert_metric_diff(registry, 1, "game_lists_entries_created_total")


@pytest.mark.django_db()
def test_updating_game_list_entry_does_not_increment_game_lists_entries_created_total(
    game_list_fixture: GameList,
) -> None:
    """Updating a GameList entry does not increment game_lists_entries_created_total."""
    registry = save_registry()
    game_list_fixture.status = GameListStatus.PLAYING
    game_list_fixture.save()
    assert_metric_diff(registry, 0, "game_lists_entries_created_total")


@pytest.mark.django_db()
def test_deleting_game_list_entry_does_not_increment_game_lists_entries_created_total(
    game_list_fixture: GameList,
) -> None:
    """Deleting a GameList entry does not increment game_lists_entries_created_total."""
    registry = save_registry()
    game_list_fixture.delete()
    assert_metric_diff(registry, 0, "game_lists_entries_created_total")
