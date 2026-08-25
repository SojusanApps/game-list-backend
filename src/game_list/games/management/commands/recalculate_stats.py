"""Management command to recalculate game statistics."""

import itertools
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Sum

from game_list.games.models import Game, GameList, GameStats
from game_list.games.tasks import recalculate_ranks


class Command(BaseCommand):  # NOSONAR(S8443) - Already inheriting from BaseCommand
    """Recalculate statistics for all games."""

    help = "Recalculates score_sum, score_count, average_score, members_count, and ranks for all games."
    BATCH_SIZE = 2000

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: ANN401, ARG002
        """Execute the command."""
        self.stdout.write("Starting statistics recalculation...")

        # 1. Ensure GameStats exist for all games
        self.stdout.write("Creating missing GameStats...")
        missing_games = Game.objects.filter(stats__isnull=True)

        # Create missing stats in batches
        missing_stats = []
        for game in missing_games.iterator(chunk_size=self.BATCH_SIZE):
            missing_stats.append(GameStats(game=game))
            if len(missing_stats) >= self.BATCH_SIZE:
                GameStats.objects.bulk_create(missing_stats)
                self.stdout.write(f"Created {len(missing_stats)} missing GameStats...")
                missing_stats = []
        if missing_stats:
            GameStats.objects.bulk_create(missing_stats)
            self.stdout.write(f"Created {len(missing_stats)} missing GameStats...")

        # 2. Update Stats in Batches (Memory Efficient)
        self.stdout.write("Updating GameStats aggregates...")

        total_stats = GameStats.objects.count()
        processed_count = 0
        update_fields = ["score_sum", "score_count", "average_score", "members_count"]

        # Use iterator to fetch objects without loading all into memory
        # itertools.batched (Py3.12+) chunks the iterator into lists of BATCH_SIZE
        stats_qs = GameStats.objects.all().select_related("game").order_by("id")

        for batch in itertools.batched(stats_qs.iterator(chunk_size=self.BATCH_SIZE), self.BATCH_SIZE, strict=False):
            # Extract Game IDs for this batch to fetch relevant aggregates
            game_ids = [stat.game_id for stat in batch]

            # Fetch aggregates ONLY for games in this batch
            aggregates = (
                GameList.objects.filter(game_id__in=game_ids)
                .values("game")
                .annotate(
                    total_score=Sum("score"),
                    count_score=Count("score"),
                    avg_score=Avg("score"),
                    total_members=Count("id"),
                )
            )

            # Map aggregates by game_id for O(1) access
            agg_map = {item["game"]: item for item in aggregates}

            # Update instances in the batch
            for stat in batch:
                data = agg_map.get(stat.game_id)
                if data:
                    stat.score_sum = data["total_score"] or 0
                    stat.score_count = data["count_score"] or 0
                    stat.average_score = data["avg_score"] or 0.0
                    stat.members_count = data["total_members"] or 0
                else:
                    # Reset if no entries
                    stat.score_sum = 0
                    stat.score_count = 0
                    stat.average_score = 0.0
                    stat.members_count = 0

            # Bulk update the batch
            GameStats.objects.bulk_update(batch, update_fields)

            processed_count += len(batch)
            self.stdout.write(f"Updated {processed_count}/{total_stats} stats...")

        self.stdout.write("Aggregates updated. Recalculating ranks...")

        # 3. Recalculate ranks (Synchronously for the command)
        recalculate_ranks()

        self.stdout.write(self.style.SUCCESS("Successfully recalculated all game statistics."))
