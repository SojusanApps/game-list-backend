"""The queryset for the game related data."""

from typing import TYPE_CHECKING, Self

from django.db.models import QuerySet

if TYPE_CHECKING:
    from game_list.games.models import Game  # noqa: F401


class GameQuerySet(QuerySet["Game"]):
    """The queryset for the Game model."""

    def with_stats(self: Self) -> Self:
        """Prefetch the game stats."""
        return self.select_related("stats")
