"""Tests for the games app celery tasks."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from my_game_list.games.tasks import nightly_igdb_import_and_recalculate

if TYPE_CHECKING:
    import pytest

EXPECTED_CALL_COUNT = 2


def test_nightly_igdb_import_and_recalculate_calls_import_then_recalculate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The task imports all IGDB data types first, then recalculates statistics."""
    mock_call_command = MagicMock()
    monkeypatch.setattr("my_game_list.games.tasks.call_command", mock_call_command)

    nightly_igdb_import_and_recalculate()

    assert mock_call_command.call_count == EXPECTED_CALL_COUNT
    first_call, second_call = mock_call_command.call_args_list
    assert first_call.args[0] == "import_data_from_igdb"
    assert first_call.args[1:] == (
        "platforms",
        "genres",
        "game_modes",
        "player_perspectives",
        "game_engines",
        "game_types",
        "game_statuses",
        "external_game_sources",
        "external_games",
        "companies",
        "games",
    )
    assert second_call.args == ("recalculate_stats",)
