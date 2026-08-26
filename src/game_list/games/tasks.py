"""Tasks for the games app."""

import logging

from celery import shared_task
from django.core.management import call_command

from game_list.games.models import GameStats

logger = logging.getLogger(__name__)


@shared_task
def recalculate_ranks() -> None:
    """Recalculate rank_position and popularity for all games."""
    stats_qs = GameStats.objects.all()
    stats_list = list(stats_qs)

    # Calculate Rank Position (by average_score desc)
    # Note: This is a simple rank (1, 2, 3...). Ties get arbitrary order here unless we sort by second key.
    # To match 'DenseRank' or 'Rank' behavior with Python is doable but 'enumerate' gives unique ranks.
    stats_list.sort(key=lambda x: (x.average_score or 0, x.game_id), reverse=True)

    # Create a list to hold updates to avoid race conditions if we were partial,
    # but here we update everything.
    for i, stat in enumerate(stats_list, start=1):
        stat.rank_position = i

    # Calculate Popularity (by members_count desc)
    stats_list.sort(key=lambda x: (x.members_count, x.game_id), reverse=True)

    for i, stat in enumerate(stats_list, start=1):
        stat.popularity = i

    # Batch update
    GameStats.objects.bulk_update(stats_list, ["rank_position", "popularity"], batch_size=1000)

    logger.info("Recalculated ranks and popularity for %d games.", len(stats_list))


@shared_task
def nightly_igdb_import_and_recalculate() -> None:
    """Import all data from IGDB then recalculate game statistics."""
    call_command(
        "import_data_from_igdb",
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
    call_command("recalculate_stats")
