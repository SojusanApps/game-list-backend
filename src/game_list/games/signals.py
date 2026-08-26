"""Signals for the games application."""

from typing import Any

from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from game_list.game_list.metrics import Metrics
from game_list.games.models import Game, GameList, GameStats


@receiver(post_save, sender=Game)
def create_game_stats(
    sender: type[Game],  # noqa: ARG001
    instance: Game,
    created: bool,  # noqa: FBT001
    **kwargs: Any,  # noqa: ARG001, ANN401
) -> None:
    """Create GameStats for new games."""
    if created:
        GameStats.objects.get_or_create(game=instance)


@receiver(post_save, sender=GameList)
def increment_game_lists_entries_created_total(
    sender: type[GameList],  # noqa: ARG001
    created: bool,  # noqa: FBT001
    **kwargs: Any,  # noqa: ARG001, ANN401
) -> None:
    """Increment game_lists_entries_created_total counter when a new GameList entry is created."""
    if created:
        Metrics.game_lists_entries_created_total.inc()


@receiver(post_save, sender=GameList)
@receiver(post_delete, sender=GameList)
def update_game_stats(
    sender: type[GameList],  # noqa: ARG001
    instance: GameList,
    **kwargs: Any,  # noqa: ARG001, ANN401
) -> None:
    """Update GameStats when a GameList is modified."""
    game = instance.game

    with transaction.atomic():
        stats, _ = GameStats.objects.get_or_create(game=game)

        # Calculate aggregates
        aggregates = GameList.objects.filter(game=game).aggregate(
            total_score=Sum("score"),
            count_score=Count("score"),
            avg_score=Avg("score"),
            total_members=Count("id"),
        )

        stats.score_sum = aggregates["total_score"] or 0
        stats.score_count = aggregates["count_score"] or 0
        stats.average_score = aggregates["avg_score"] or 0.0
        stats.members_count = aggregates["total_members"] or 0
        stats.save()
