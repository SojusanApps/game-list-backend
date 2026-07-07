"""This module contains the admin models for game related data."""

from typing import ClassVar

from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from my_game_list.games.models import (
    Company,
    ExternalGameSource,
    Game,
    GameEngine,
    GameFollow,
    GameList,
    GameMedia,
    GameMode,
    GameReview,
    GameStatus,
    GameType,
    Genre,
    Platform,
    PlayerPerspective,
    TranslationSuggestion,
)
from my_game_list.my_game_list.admin import BaseDictionaryModelAdmin


@admin.register(Company)
class CompanyAdmin(BaseDictionaryModelAdmin):
    """Admin model for the company model."""

    readonly_fields = (*BaseDictionaryModelAdmin.readonly_fields, "company_logo_tag", "igdb_id", "igdb_updated_at")
    list_display = (*BaseDictionaryModelAdmin.list_display, "company_logo_tag")


@admin.register(GameFollow)
class GameFollowAdmin(admin.ModelAdmin[GameFollow]):
    """Admin model for the game follow model."""

    readonly_fields = ("id",)
    search_fields = (*readonly_fields, "game__title_en", "game__title_pl", "user__username")
    raw_id_fields = ("game", "user")
    list_filter = ("created_at",)
    list_display = (*readonly_fields, *list_filter, *raw_id_fields)


@admin.register(GameList)
class GameListAdmin(admin.ModelAdmin[GameList]):
    """Admin model for the game list model."""

    readonly_fields = ("id",)
    search_fields = (*readonly_fields, "game__title_en", "game__title_pl", "user__username")
    raw_id_fields = ("game", "user")
    list_filter = ("status", "created_at", "last_modified_at", "score")
    list_display = (*readonly_fields, *list_filter, "playtime", *raw_id_fields)


@admin.register(GameReview)
class GameReviewAdmin(admin.ModelAdmin[GameReview]):
    """Admin model for the game review model."""

    readonly_fields = ("id",)
    search_fields = (*readonly_fields, "game__title_en", "game__title_pl", "user__username")
    raw_id_fields = ("game", "user")
    list_filter = ("created_at",)
    list_display = (*readonly_fields, *list_filter, *raw_id_fields)


@admin.register(Game)
class GameAdmin(TabbedTranslationAdmin[Game]):
    """Admin model for the game model."""

    readonly_fields = ("id", "cover_image_tag", "cover_image_id", "igdb_id", "igdb_updated_at")
    search_fields = (
        "id",
        "title_en",
        "title_pl",
        "igdb_id",
        "publisher__name_en",
        "publisher__name_pl",
        "developer__name_en",
        "developer__name_pl",
        "genres__name_en",
        "genres__name_pl",
        "platforms__name_en",
        "platforms__name_pl",
    )
    raw_id_fields = ("external_games",)
    autocomplete_fields = (
        "publisher",
        "developer",
        "bundles",
        "dlcs",
        "expanded_games",
        "expansions",
        "forks",
        "ports",
        "standalone_expansions",
        "game_engines",
        "game_modes",
        "player_perspectives",
        "genres",
        "platforms",
        "parent_game",
    )
    list_filter = ("created_at", "last_modified_at", "release_date")
    list_display = (
        *readonly_fields,
        *list_filter,
        "publisher",
        "developer",
        "title_en",
        "title_pl",
        "cover_image_id",
    )


@admin.register(Genre)
class GenreAdmin(BaseDictionaryModelAdmin):
    """Admin model for the genre model."""

    readonly_fields = (*BaseDictionaryModelAdmin.readonly_fields, "igdb_id", "igdb_updated_at")
    list_display = (*BaseDictionaryModelAdmin.list_display, "igdb_id")


@admin.register(Platform)
class PlatformAdmin(BaseDictionaryModelAdmin):
    """Admin model for the platform model."""

    readonly_fields = (*BaseDictionaryModelAdmin.readonly_fields, "igdb_id", "igdb_updated_at")
    list_display = (*BaseDictionaryModelAdmin.list_display, "abbreviation", "igdb_id")


@admin.register(GameMedia)
class GameMediaAdmin(BaseDictionaryModelAdmin):
    """Admin model for the game media model."""

    readonly_fields = (*BaseDictionaryModelAdmin.readonly_fields,)
    list_display = (*BaseDictionaryModelAdmin.list_display,)


@admin.register(GameEngine)
class GameEngineAdmin(BaseDictionaryModelAdmin):
    """Admin model for the game engine model."""

    readonly_fields = (*BaseDictionaryModelAdmin.readonly_fields, "igdb_id", "igdb_updated_at")
    list_display = (*BaseDictionaryModelAdmin.list_display, "igdb_id")


@admin.register(GameMode)
class GameModeAdmin(BaseDictionaryModelAdmin):
    """Admin model for the game mode model."""

    readonly_fields = (*BaseDictionaryModelAdmin.readonly_fields, "igdb_id", "igdb_updated_at")
    list_display = (*BaseDictionaryModelAdmin.list_display, "igdb_id")


@admin.register(PlayerPerspective)
class PlayerPerspectiveAdmin(BaseDictionaryModelAdmin):
    """Admin model for the player perspective model."""

    readonly_fields = (*BaseDictionaryModelAdmin.readonly_fields, "igdb_id", "igdb_updated_at")
    list_display = (*BaseDictionaryModelAdmin.list_display, "igdb_id")


@admin.register(ExternalGameSource)
class ExternalGameSourceAdmin(BaseDictionaryModelAdmin):
    """Admin model for the external game source model."""

    readonly_fields = (*BaseDictionaryModelAdmin.readonly_fields, "igdb_id", "igdb_updated_at")
    list_display = (*BaseDictionaryModelAdmin.list_display, "igdb_id")


@admin.register(GameStatus)
class GameStatusAdmin(BaseDictionaryModelAdmin):
    """Admin model for the game status model."""

    readonly_fields: ClassVar[tuple[str, ...]] = ("id", "igdb_id", "igdb_updated_at")
    search_fields: ClassVar[tuple[str, ...]] = ("status_en", "status_pl")
    list_display: tuple[str, ...] = (*readonly_fields, *search_fields)


@admin.register(GameType)
class GameTypeAdmin(BaseDictionaryModelAdmin):
    """Admin model for the game type model."""

    readonly_fields: ClassVar[tuple[str, ...]] = ("id", "igdb_id", "igdb_updated_at")
    search_fields: ClassVar[tuple[str, ...]] = ("type_en", "type_pl")
    list_display: tuple[str, ...] = (*readonly_fields, *search_fields)


@admin.register(TranslationSuggestion)
class TranslationSuggestionAdmin(admin.ModelAdmin[TranslationSuggestion]):
    """Admin model for the translation suggestion model."""

    readonly_fields = ("id", "current_value", "submitted_at", "reviewed_at")
    search_fields = (*readonly_fields, "game__title_en", "game__title_pl", "submitted_by__username")
    raw_id_fields = ("game", "submitted_by", "reviewed_by")
    list_filter = ("field", "status", "submitted_at")
    list_display = (*readonly_fields, *list_filter, *raw_id_fields)
