"""Filters for game related data."""

from typing import Any

from django.db.models import F, Q, QuerySet, Value
from django.db.models.functions import Coalesce, NullIf
from django_filters import rest_framework as filters
from modeltranslation.utils import build_localized_fieldname, get_language

from game_list.game_list.filters import BaseLookupFilterSet, BilingualModelMultipleChoiceFilter
from game_list.games.models import (
    Company,
    ExternalGameSource,
    Game,
    GameEngine,
    GameFollow,
    GameList,
    GameListStatus,
    GameMedia,
    GameMode,
    GameReview,
    GameReviewRecommendation,
    GameStatus,
    GameType,
    Genre,
    Platform,
    PlayerPerspective,
    ReviewLanguage,
    TranslationSuggestion,
)
from game_list.games.search import filter_queryset_by_title


class CompanyFilterSet(BaseLookupFilterSet):
    """Filter set for company model."""

    class Meta(BaseLookupFilterSet.Meta):
        """Meta class for CompanyFilterSet."""

        model = Company
        fields: tuple[str, ...] = (*BaseLookupFilterSet.Meta.fields, "igdb_id")


class GameFollowFilterSet(filters.FilterSet):
    """FilterSet for game follow model."""

    game = filters.NumberFilter(field_name="game__id")
    user = filters.NumberFilter(field_name="user_id")

    class Meta:
        """Meta class for game follow filter set."""

        model = GameFollow
        fields = (
            "id",
            "game",
            "user",
        )


def _game_title_sort_key() -> Coalesce:
    """Return the related game's title in the active language, falling back to English when it is blank.

    `GameList` querysets aren't rewritten by modeltranslation, so the language column is picked explicitly.
    This mirrors what `Game.title` resolves to in the serializer.
    """
    localized_title = F(f"game__{build_localized_fieldname('title', get_language())}")
    return Coalesce(NullIf(localized_title, Value("")), F("game__title_en"))


class GameListFilterSet(filters.FilterSet):
    """FilterSet for game list model."""

    status = filters.MultipleChoiceFilter(choices=GameListStatus.choices)
    game = filters.NumberFilter(field_name="game__id")
    user = filters.NumberFilter(field_name="user__id")

    title = filters.CharFilter(method="filter_title")
    release_date = filters.DateFromToRangeFilter(field_name="game__release_date")
    publisher = filters.CharFilter(method="filter_publisher")
    developer = filters.CharFilter(method="filter_developer")
    genres = BilingualModelMultipleChoiceFilter(
        field_name="game__genres",
        queryset=Genre.objects.all(),
    )
    platforms = BilingualModelMultipleChoiceFilter(
        field_name="game__platforms",
        queryset=Platform.objects.all(),
    )
    game_type = BilingualModelMultipleChoiceFilter(
        field_name="game__game_type",
        queryset=GameType.objects.all(),
        en_field="type_en",
        pl_field="type_pl",
    )
    game_status = BilingualModelMultipleChoiceFilter(
        field_name="game__game_status",
        queryset=GameStatus.objects.all(),
        en_field="status_en",
        pl_field="status_pl",
    )
    game_engines = BilingualModelMultipleChoiceFilter(
        field_name="game__game_engines",
        queryset=GameEngine.objects.all(),
    )
    game_modes = BilingualModelMultipleChoiceFilter(
        field_name="game__game_modes",
        queryset=GameMode.objects.all(),
    )
    player_perspectives = BilingualModelMultipleChoiceFilter(
        field_name="game__player_perspectives",
        queryset=PlayerPerspective.objects.all(),
    )
    external_games = BilingualModelMultipleChoiceFilter(
        field_name="game__external_games__external_game_source",
        queryset=ExternalGameSource.objects.all(),
    )

    def filter_title(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by game title using fuzzy matching, best match first."""
        return filter_queryset_by_title(queryset, value, game_field="game__")

    def filter_publisher(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by publisher name in English or Polish."""
        return queryset.filter(
            Q(game__publisher__name_en__icontains=value) | Q(game__publisher__name_pl__icontains=value),
        )

    def filter_developer(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by developer name in English or Polish."""
        return queryset.filter(
            Q(game__developer__name_en__icontains=value) | Q(game__developer__name_pl__icontains=value),
        )

    ordering = filters.OrderingFilter(
        fields=(("score", "score"), ("title", "title")),
        method="filter_ordering",
    )

    def filter_ordering(self, queryset: QuerySet[Any], _name: str, value: list[str]) -> QuerySet[Any]:
        """Order by the requested `score` and/or `title` keys, in the order given.

        Unscored entries always come last, whatever the score direction. Unless `title` is itself requested, ties are
        broken by game title A-Z; `id` is always the last key, so pages stay stable. An explicit ordering replaces
        the best-match-first order of the `title` filter.
        """
        sort_keys: dict[str, F | Coalesce] = {"score": F("score"), "title": _game_title_sort_key()}
        ordering = []
        for term in value:
            key = sort_keys[term.removeprefix("-")]
            ordering.append(key.desc(nulls_last=True) if term.startswith("-") else key.asc(nulls_last=True))
        if not any(term.removeprefix("-") == "title" for term in value):
            ordering.append(sort_keys["title"].asc())
        return queryset.order_by(*ordering, "id")

    class Meta:
        """Meta class for game list filter set."""

        model = GameList
        fields = (
            "id",
            "status",
            "game",
            "user",
            "title",
            "release_date",
            "publisher",
            "developer",
            "genres",
            "platforms",
            "game_type",
            "game_status",
            "game_engines",
            "game_modes",
            "player_perspectives",
        )


class GameReviewFilterSet(filters.FilterSet):
    """FilterSet for game review model."""

    score = filters.NumberFilter()
    game = filters.NumberFilter(field_name="game__id")
    user = filters.NumberFilter(field_name="user__id")
    recommendation = filters.ChoiceFilter(choices=GameReviewRecommendation.choices)
    language = filters.ChoiceFilter(choices=ReviewLanguage.choices)

    class Meta:
        """Meta class for game review filter set."""

        model = GameReview
        fields = (
            "id",
            "score",
            "game",
            "user",
            "recommendation",
            "language",
        )


class GameFilterSet(filters.FilterSet):
    """FilterSet for game model."""

    title = filters.CharFilter(method="filter_title")
    release_date = filters.DateFromToRangeFilter()
    publisher = filters.CharFilter(method="filter_publisher")
    developer = filters.CharFilter(method="filter_developer")
    genres = BilingualModelMultipleChoiceFilter(
        field_name="genres",
        queryset=Genre.objects.all(),
    )
    platforms = BilingualModelMultipleChoiceFilter(
        field_name="platforms",
        queryset=Platform.objects.all(),
    )
    game_type = BilingualModelMultipleChoiceFilter(
        field_name="game_type",
        queryset=GameType.objects.all(),
        en_field="type_en",
        pl_field="type_pl",
    )
    game_status = BilingualModelMultipleChoiceFilter(
        field_name="game_status",
        queryset=GameStatus.objects.all(),
        en_field="status_en",
        pl_field="status_pl",
    )
    game_engines = BilingualModelMultipleChoiceFilter(
        field_name="game_engines",
        queryset=GameEngine.objects.all(),
    )
    game_modes = BilingualModelMultipleChoiceFilter(
        field_name="game_modes",
        queryset=GameMode.objects.all(),
    )
    player_perspectives = BilingualModelMultipleChoiceFilter(
        field_name="player_perspectives",
        queryset=PlayerPerspective.objects.all(),
    )
    external_games = BilingualModelMultipleChoiceFilter(
        field_name="external_games__external_game_source",
        queryset=ExternalGameSource.objects.all(),
    )

    def filter_title(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by game title using fuzzy matching, best match first."""
        return filter_queryset_by_title(queryset, value)

    def filter_publisher(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by publisher name in English or Polish."""
        return queryset.filter(Q(publisher__name_en__icontains=value) | Q(publisher__name_pl__icontains=value))

    def filter_developer(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by developer name in English or Polish."""
        return queryset.filter(Q(developer__name_en__icontains=value) | Q(developer__name_pl__icontains=value))

    ordering = filters.OrderingFilter(
        fields=(
            ("created_at", "created_at"),
            ("stats__rank_position", "rank_position"),
            ("stats__popularity", "popularity"),
            ("release_date", "release_date"),
        ),
    )

    class Meta:
        """Meta class for GameFilterSet."""

        model = Game
        fields = (
            "id",
            "title",
            "release_date",
            "publisher",
            "developer",
            "genres",
            "platforms",
            "game_type",
            "game_status",
            "game_engines",
            "game_modes",
            "player_perspectives",
        )


class GenreFilterSet(BaseLookupFilterSet):
    """Filter set for genre model."""

    class Meta(BaseLookupFilterSet.Meta):
        """Meta class for GenreFilterSet."""

        model = Genre


class PlatformFilterSet(BaseLookupFilterSet):
    """Filter set for platform model."""

    class Meta(BaseLookupFilterSet.Meta):
        """Meta class for PlatformFilterSet."""

        model = Platform


class GameTypeFilterSet(filters.FilterSet):
    """Filter set for game type model."""

    type = filters.CharFilter(method="filter_type")

    def filter_type(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by type in English or Polish."""
        return queryset.filter(Q(type_en__icontains=value) | Q(type_pl__icontains=value))

    class Meta:
        """Meta class for GameTypeFilterSet."""

        model = GameType
        fields = ("id", "type", "igdb_id")


class GameStatusFilterSet(filters.FilterSet):
    """Filter set for game status model."""

    status = filters.CharFilter(method="filter_status")

    def filter_status(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by status in English or Polish."""
        return queryset.filter(Q(status_en__icontains=value) | Q(status_pl__icontains=value))

    class Meta:
        """Meta class for GameStatusFilterSet."""

        model = GameStatus
        fields = ("id", "status", "igdb_id")


class GameEngineFilterSet(BaseLookupFilterSet):
    """Filter set for game engine model."""

    class Meta(BaseLookupFilterSet.Meta):
        """Meta class for GameEngineFilterSet."""

        model = GameEngine
        fields = (*BaseLookupFilterSet.Meta.fields, "igdb_id")


class GameModeFilterSet(BaseLookupFilterSet):
    """Filter set for game mode model."""

    class Meta(BaseLookupFilterSet.Meta):
        """Meta class for GameModeFilterSet."""

        model = GameMode
        fields = (*BaseLookupFilterSet.Meta.fields, "igdb_id")


class PlayerPerspectiveFilterSet(BaseLookupFilterSet):
    """Filter set for player perspective model."""

    class Meta(BaseLookupFilterSet.Meta):
        """Meta class for PlayerPerspectiveFilterSet."""

        model = PlayerPerspective
        fields = (*BaseLookupFilterSet.Meta.fields, "igdb_id")


class ExternalGameSourceFilterSet(BaseLookupFilterSet):
    """Filter set for external game source model."""

    class Meta(BaseLookupFilterSet.Meta):
        """Meta class for ExternalGameSourceFilterSet."""

        model = ExternalGameSource
        fields = (*BaseLookupFilterSet.Meta.fields, "igdb_id")


class GameMediaFilterSet(BaseLookupFilterSet):
    """Filter set for game media model."""

    class Meta(BaseLookupFilterSet.Meta):
        """Meta class for GameMediaFilterSet."""

        model = GameMedia


class TranslationSuggestionFilterSet(filters.FilterSet):
    """Filter set for translation suggestion model."""

    game = filters.NumberFilter(field_name="game__id")
    submitted_by = filters.NumberFilter(field_name="submitted_by__id")

    class Meta:
        """Meta class for translation suggestion filter set."""

        model = TranslationSuggestion
        fields = (
            "id",
            "game",
            "field",
            "status",
            "submitted_by",
        )
