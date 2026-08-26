"""Translation options for game-related models."""

from modeltranslation.translator import TranslationOptions, register

from game_list.games.models import (
    Company,
    ExternalGameSource,
    Game,
    GameEngine,
    GameMedia,
    GameMode,
    GameStatus,
    GameType,
    Genre,
    Platform,
    PlayerPerspective,
)


class NameTranslationOptions(TranslationOptions):
    """Shared translation options for lookup models with a name field."""

    fields = ("name",)


@register(Company)
class CompanyTranslationOptions(NameTranslationOptions):
    """Translation options for the Company model."""


@register(ExternalGameSource)
class ExternalGameSourceTranslationOptions(NameTranslationOptions):
    """Translation options for the ExternalGameSource model."""


@register(GameEngine)
class GameEngineTranslationOptions(NameTranslationOptions):
    """Translation options for the GameEngine model."""


@register(GameMedia)
class GameMediaTranslationOptions(NameTranslationOptions):
    """Translation options for the GameMedia model."""


@register(GameMode)
class GameModeTranslationOptions(NameTranslationOptions):
    """Translation options for the GameMode model."""


@register(Genre)
class GenreTranslationOptions(NameTranslationOptions):
    """Translation options for the Genre model."""


@register(Platform)
class PlatformTranslationOptions(NameTranslationOptions):
    """Translation options for the Platform model."""


@register(PlayerPerspective)
class PlayerPerspectiveTranslationOptions(NameTranslationOptions):
    """Translation options for the PlayerPerspective model."""


@register(GameType)
class GameTypeTranslationOptions(TranslationOptions):
    """Translation options for the GameType model."""

    fields = ("type",)


@register(GameStatus)
class GameStatusTranslationOptions(TranslationOptions):
    """Translation options for the GameStatus model."""

    fields = ("status",)


@register(Game)
class GameTranslationOptions(TranslationOptions):
    """Translation options for the Game model."""

    fields = ("title", "summary")
