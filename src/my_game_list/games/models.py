"""This module contains the models for the game related data."""

from typing import TYPE_CHECKING, Any, ClassVar, Self
from uuid import uuid4

from django.conf import settings
from django.contrib import admin
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.html import format_html
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta

from my_game_list.games.querysets import GameQuerySet
from my_game_list.games.utils import normalize_title
from my_game_list.my_game_list.igdb_integration import IGDBImageSize, get_image_url
from my_game_list.my_game_list.models import BaseDictionaryModel, BaseModel


class IGDBModel(models.Model):
    """Base IGDB model.

    The IGDB models have an igdb_id field that stores the ID of the object in IGDB
    and an igdb_updated_at field that stores the last time the object was updated in IGDB.
    The `updated_at` field can be used to determine if the object needs to be updated
    from IGDB or not.
    """

    igdb_id = models.PositiveIntegerField(
        _("igdb id"),
        unique=True,
        help_text="The ID of this record in the IGDB database.",
    )
    igdb_updated_at = models.DateTimeField(
        _("igdb last updated at"),
        help_text="Timestamp of the last changes in IGDB.",
    )

    class Meta(TypedModelMeta):
        """Meta data for dictionary models."""

        abstract = True

    def __str__(self: Self) -> str:
        """String representation of dictionary models."""
        return f"{self.igdb_id}"


class Company(BaseDictionaryModel, IGDBModel):
    """Data about company."""

    name = models.CharField(_("name"), max_length=255, help_text="The company's name.")
    company_logo_id = models.CharField(
        _("company logo id"),
        max_length=255,
        blank=True,
        help_text="The IGDB logo ID used to construct the company logo image URL.",
    )
    slug = models.SlugField(
        _("slug"),
        max_length=512,
        unique=True,
        blank=True,
        help_text="URL-safe identifier, auto-generated from the company name.",
    )

    if TYPE_CHECKING:
        name_en: str
        name_pl: str

    class Meta(BaseDictionaryModel.Meta):
        """Meta data for the company model."""

        verbose_name = _("company")
        verbose_name_plural = _("companies")

    def save(self: Self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Save the company."""
        if not self.slug and self.name_en:
            self.slug = slugify(self.name_en)
        if not self.slug:
            self.slug = str(uuid4())
        super().save(*args, **kwargs)

    @property
    @admin.display(description="Company logo preview")
    def company_logo_tag(self: Self) -> str:
        """Used in admin model to have a image preview."""
        if self.company_logo_id:
            return format_html(
                '<img src={} width="284" height="160">',
                get_image_url(self.company_logo_id, IGDBImageSize.LOGO_MED_284_160),
            )
        return ""


class GameFollow(BaseModel):
    """Game follow model.

    Contains the games followed by a user. Following a game means that
    the user wants to have notifications about this game.
    """

    created_at = models.DateTimeField(_("creation time"), auto_now_add=True)

    game = models.ForeignKey(
        "Game",
        on_delete=models.PROTECT,
        related_name="follow_list",
        help_text="The game being followed.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="games_followed",
        help_text="The user following the game.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the game follow model."""

        verbose_name = _("game follow")
        verbose_name_plural = _("games follows")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("game", "user"), name="unique_game_user_in_game_follow"),
        ]

    def __str__(self: Self) -> str:
        """String representation of the game follow model."""
        return f"{self.user.username} - {self.game.title}"


class GameListStatus(models.TextChoices):
    """Statuses for games in a game list."""

    COMPLETED = "C", _("Completed")
    PLAN_TO_PLAY = "PTP", _("Plan to play")
    PLAYING = "P", _("Playing")
    DROPPED = "D", _("Dropped")
    ON_HOLD = "OH", _("On hold")


class GameMedia(BaseDictionaryModel):
    """Data about media on which the game is owned."""

    class Meta(BaseDictionaryModel.Meta):
        """Meta data for the game owned on model."""

        verbose_name = _("game media")
        verbose_name_plural = _("game medias")


class GameList(BaseModel):
    """A game list model. Contains the list of games for user."""

    score = models.PositiveIntegerField(
        _("score"),
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        null=True,
        blank=True,
        help_text="The user's score for this game, between 1 and 10.",
    )
    status = models.CharField(
        _("status"),
        max_length=3,
        choices=GameListStatus.choices,
        help_text="The user's current play status (Completed, Plan to Play, Playing, Dropped, On Hold).",
    )
    description = models.CharField(
        _("description"),
        max_length=200,
        blank=True,
        help_text="Optional personal notes about this game.",
    )
    completed_at = models.DateField(
        _("completed at"),
        null=True,
        blank=True,
        help_text="The date the user completed this game.",
    )
    started_at = models.DateField(
        _("started at"),
        null=True,
        blank=True,
        help_text="The date the user started playing this game.",
    )
    playtime = models.PositiveIntegerField(
        _("playtime"),
        null=True,
        blank=True,
        help_text="The number of minutes played.",
    )
    created_at = models.DateTimeField(_("creation time"), auto_now_add=True)
    last_modified_at = models.DateTimeField(_("last modified"), auto_now=True)

    game = models.ForeignKey(
        "Game",
        on_delete=models.CASCADE,
        related_name="game_lists",
        help_text="The game this list entry refers to.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_lists",
        help_text="The user who owns this game list entry.",
    )
    owned_on = models.ManyToManyField(
        GameMedia,
        related_name="game_lists",
        help_text="The media formats on which the user owns this game.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for game list model."""

        verbose_name = _("game list")
        verbose_name_plural = _("game lists")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("game", "user"), name="unique_game_user_in_game_list"),
        ]

    def __str__(self: Self) -> str:
        """String representation of the game list model."""
        return f"{self.user.username} - {self.game.title}"


class GameReview(BaseModel):
    """Contains reviews for games."""

    created_at = models.DateTimeField(_("creation time"), auto_now_add=True)
    review = models.TextField(
        _("review"),
        blank=True,
        max_length=1000,
        help_text="The review text.",
    )

    game = models.ForeignKey(
        "Game",
        on_delete=models.PROTECT,
        related_name="reviews",
        help_text="The game being reviewed.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews",
        help_text="The user who wrote the review.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for game review model."""

        verbose_name = _("game review")
        verbose_name_plural = _("games reviews")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("game", "user"), name="unique_game_user_in_game_review"),
        ]

    def __str__(self: Self) -> str:
        """String representation of the game review model."""
        return f"{self.user.username} - {self.game.title}"


class Genre(BaseDictionaryModel, IGDBModel):
    """Data about game genres."""

    class Meta(BaseDictionaryModel.Meta):
        """Meta data for the genre model."""

        verbose_name = _("genre")
        verbose_name_plural = _("genres")


class Platform(BaseDictionaryModel, IGDBModel):
    """Data about game platforms."""

    abbreviation = models.CharField(
        _("abbreviation"),
        max_length=255,
        blank=True,
        help_text="A short abbreviation for the platform name (e.g. PS5, PC).",
    )

    class Meta(BaseDictionaryModel.Meta):
        """Meta data for the platform model."""

        verbose_name = _("platform")
        verbose_name_plural = _("platforms")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["abbreviation"],
                name="unique_abbreviation",
                condition=models.Q(abbreviation__isnull=False, abbreviation__gt=""),
            ),
        ]


class GameEngine(IGDBModel):
    """Data about game engines."""

    name = models.CharField(_("name"), max_length=255, help_text="The game engine's name.")

    class Meta(BaseDictionaryModel.Meta):
        """Meta data for the game engine model."""

        verbose_name = _("game engine")
        verbose_name_plural = _("game engines")


class GameMode(BaseDictionaryModel, IGDBModel):
    """Data about game modes."""

    class Meta(BaseDictionaryModel.Meta):
        """Meta data for the game mode model."""

        verbose_name = _("game mode")
        verbose_name_plural = _("game modes")


class PlayerPerspective(BaseDictionaryModel, IGDBModel):
    """Data about player perspectives."""

    class Meta(BaseDictionaryModel.Meta):
        """Meta data for the player perspective model."""

        verbose_name = _("player perspective")
        verbose_name_plural = _("player perspectives")


class GameStats(models.Model):
    """Data about game statistics."""

    game = models.OneToOneField(
        "Game",
        on_delete=models.CASCADE,
        related_name="stats",
        help_text="The game this statistics record belongs to.",
    )

    # Aggregates (Updated via Signals/Save)
    score_sum = models.BigIntegerField(
        _("score sum"),
        default=0,
        help_text="The sum of all user scores, used for average calculation.",
    )
    score_count = models.PositiveIntegerField(
        _("score count"),
        default=0,
        help_text="The number of users who have scored this game.",
    )
    average_score = models.DecimalField(
        _("average score"),
        max_digits=4,
        decimal_places=2,
        default=0,
        db_index=True,
        help_text="The computed average score across all user ratings.",
    )
    members_count = models.PositiveIntegerField(
        _("members count"),
        default=0,
        db_index=True,
        help_text="The number of users who have this game in their game list.",
    )

    # Ranks (Updated via Celery)
    popularity = models.PositiveIntegerField(
        _("popularity"),
        null=True,
        db_index=True,
        help_text="The game's popularity rank, updated periodically by a background task.",
    )
    rank_position = models.PositiveIntegerField(
        _("rank position"),
        null=True,
        db_index=True,
        help_text="The game's position in the all-time ranking, updated periodically.",
    )

    class Meta(TypedModelMeta):
        """Meta data for the game stats model."""

        verbose_name = _("game stats")
        verbose_name_plural = _("game stats")

    def __str__(self: Self) -> str:
        """String representation of the game stats model."""
        return f"{self.game.title} - Stats"


class GameType(BaseModel, IGDBModel):
    """Data about game types."""

    type = models.CharField(
        _("type"),
        max_length=255,
        unique=True,
        help_text="The game type name (e.g. Main Game, DLC, Expansion).",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the game type model."""

        verbose_name = _("game type")
        verbose_name_plural = _("game types")

    def __str__(self: Self) -> str:
        """String representation of the game type model."""
        return self.type


class GameStatus(BaseModel, IGDBModel):
    """Data about game statuses."""

    status = models.CharField(
        _("status"),
        max_length=255,
        unique=True,
        help_text="The release status name (e.g. Released, Alpha, Early Access).",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the game status model."""

        verbose_name = _("game status")
        verbose_name_plural = _("game statuses")

    def __str__(self: Self) -> str:
        """String representation of the game status model."""
        return self.status


class ExternalGameSource(BaseDictionaryModel, IGDBModel):
    """Data about external game sources."""

    class Meta(BaseDictionaryModel.Meta):
        """Meta data for the external game source model."""

        verbose_name = _("external game source")
        verbose_name_plural = _("external game sources")


class ExternalGame(BaseModel, IGDBModel):
    """Data about external games."""

    external_game_source = models.ForeignKey(
        ExternalGameSource,
        on_delete=models.CASCADE,
        related_name="external_games",
        help_text="The external platform where this game is listed (e.g. Steam, GOG).",
    )
    external_id = models.CharField(
        _("external id"),
        max_length=255,
        help_text="The game's identifier on the external platform.",
    )
    url = models.URLField(
        _("url"),
        max_length=1024,
        blank=True,
        help_text="A direct link to the game on the external platform.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the external game model."""

        verbose_name = _("external game")
        verbose_name_plural = _("external games")


class TranslationSuggestionField(models.TextChoices):
    """The Game fields that can be targeted by a translation suggestion."""

    TITLE = "title", _("Title")
    SUMMARY = "summary", _("Summary")


class TranslationSuggestionStatus(models.TextChoices):
    """The lifecycle states of a translation suggestion."""

    PENDING = "pending", _("Pending")
    ACCEPTED = "accepted", _("Accepted")
    REJECTED = "rejected", _("Rejected")
    WITHDRAWN = "withdrawn", _("Withdrawn")


class TranslationSuggestion(BaseModel):
    """A user-submitted proposal for a new Polish value of a Game's title or summary."""

    Field = TranslationSuggestionField
    Status = TranslationSuggestionStatus

    game = models.ForeignKey(
        "Game",
        on_delete=models.CASCADE,
        related_name="translation_suggestions",
        help_text="The game this suggestion targets.",
    )
    field = models.CharField(
        _("field"),
        max_length=10,
        choices=TranslationSuggestionField.choices,
        help_text="The Game field this suggestion proposes a new Polish value for.",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="translation_suggestions",
        help_text="The user who submitted this suggestion.",
    )
    current_value = models.TextField(
        _("current value"),
        blank=True,
        help_text="A snapshot of the field's value at the time this suggestion was submitted.",
    )
    proposed_value = models.TextField(
        _("proposed value"),
        blank=True,
        help_text="The proposed new Polish value for the field.",
    )
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=TranslationSuggestionStatus.choices,
        default=TranslationSuggestionStatus.PENDING,
        help_text="The current lifecycle state of this suggestion.",
    )
    submitted_at = models.DateTimeField(_("submitted at"), auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_translation_suggestions",
        null=True,
        blank=True,
        help_text="The admin who accepted or rejected this suggestion.",
    )
    reviewed_at = models.DateTimeField(
        _("reviewed at"),
        null=True,
        blank=True,
        help_text="The time this suggestion was accepted or rejected.",
    )
    rejection_reason = models.CharField(
        _("rejection reason"),
        max_length=500,
        blank=True,
        help_text="Optional reason given by the admin when rejecting this suggestion.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the translation suggestion model."""

        verbose_name = _("translation suggestion")
        verbose_name_plural = _("translation suggestions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("game", "field", "submitted_by"),
                condition=models.Q(status=TranslationSuggestionStatus.PENDING),
                name="unique_pending_suggestion_per_user_game_field",
            ),
        ]

    def __str__(self: Self) -> str:
        """String representation of the translation suggestion model."""
        return f"{self.game.title} - {self.field} ({self.status})"


class Game(BaseModel, IGDBModel):
    """A model containing data about games."""

    title = models.CharField(_("title"), max_length=255, help_text="The game's title.")
    created_at = models.DateTimeField(_("creation time"), auto_now_add=True, db_index=True)
    last_modified_at = models.DateTimeField(_("last modified"), auto_now=True)
    release_date = models.DateField(
        _("release date"),
        blank=True,
        null=True,
        help_text="The worldwide release date of the game.",
    )
    cover_image_id = models.CharField(
        _("cover image id"),
        max_length=255,
        blank=True,
        help_text="The IGDB cover image ID used to construct the cover image URL.",
    )
    summary = models.TextField(
        _("summary"),
        blank=True,
        max_length=2000,
        help_text="A short description or synopsis of the game.",
    )
    slug = models.SlugField(
        _("slug"),
        max_length=512,
        unique=True,
        blank=True,
        help_text="URL-safe identifier, auto-generated from the English title.",
    )
    search_title = models.CharField(
        _("search title"),
        max_length=511,
        blank=True,
        default="",
        help_text="Normalized title used for fuzzy search (lowercase, no diacritics, no special chars).",
    )

    game_type = models.ForeignKey(
        GameType,
        on_delete=models.SET_NULL,
        related_name="games",
        blank=True,
        null=True,
        help_text="The game type (Main Game, DLC, Expansion, etc.).",
    )
    game_status = models.ForeignKey(
        GameStatus,
        on_delete=models.SET_NULL,
        related_name="games",
        blank=True,
        null=True,
        help_text="The current release status of the game.",
    )

    parent_game = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children_games",
        help_text="The parent game this record is a DLC, expansion, or port of.",
    )

    bundles = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="bundled_in",
        blank=True,
        help_text="Bundles that include this game.",
    )
    dlcs = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="dlc_of",
        blank=True,
        help_text="DLC additions for this game.",
    )
    expanded_games = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="expanded_by",
        blank=True,
        help_text="Games expanded by this game.",
    )
    expansions = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="expansion_of",
        blank=True,
        help_text="Expansions of this game.",
    )
    forks = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="fork_of",
        blank=True,
        help_text="Fork versions derived from this game.",
    )
    ports = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="port_of",
        blank=True,
        help_text="Platform ports of this game.",
    )
    standalone_expansions = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="standalone_expansion_of",
        blank=True,
        help_text="Standalone expansions of this game.",
    )

    game_engines = models.ManyToManyField(
        GameEngine,
        related_name="games",
        blank=True,
        help_text="Game engines used to build this game.",
    )
    game_modes = models.ManyToManyField(
        GameMode,
        related_name="games",
        blank=True,
        help_text="Supported game modes (single-player, multiplayer, co-op, etc.).",
    )
    player_perspectives = models.ManyToManyField(
        PlayerPerspective,
        related_name="games",
        blank=True,
        help_text="Supported player perspectives (first-person, third-person, etc.).",
    )
    external_games = models.ManyToManyField(
        ExternalGame,
        related_name="games",
        blank=True,
        help_text="Links to external platforms where this game is available.",
    )
    screenshots = ArrayField(
        models.CharField(max_length=255),
        default=list,
        blank=True,
        help_text="IGDB screenshot IDs for this game.",
    )

    publisher = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="games_published",
        blank=True,
        null=True,
        help_text="The company that published this game.",
    )
    developer = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="games_developed",
        blank=True,
        null=True,
        help_text="The company that developed this game.",
    )
    genres = models.ManyToManyField(
        Genre,
        related_name="games",
        help_text="Genres this game belongs to.",
    )
    platforms = models.ManyToManyField(
        Platform,
        related_name="games",
        help_text="Platforms this game is available on.",
    )

    objects = GameQuerySet.as_manager()

    if TYPE_CHECKING:
        title_en: str
        title_pl: str
        summary_en: str
        summary_pl: str

    class Meta(BaseModel.Meta):
        """Meta data for the game model."""

        verbose_name = _("game")
        verbose_name_plural = _("games")
        indexes: ClassVar = [
            GinIndex(fields=["search_title"], name="games_game_search_title_gin", opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self: Self) -> str:
        """String representation of the game model."""
        return self.title

    def save(self: Self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Save the game."""
        if not self.slug and self.title_en:
            self.slug = slugify(self.title_en)
        if not self.slug:
            self.slug = str(uuid4())
        parts = {normalize_title(t) for t in (self.title_en or "", self.title_pl or "") if t}
        self.search_title = " ".join(sorted(parts))
        super().save(*args, **kwargs)

    @property
    @admin.display(description="Cover image preview")
    def cover_image_tag(self: Self) -> str:
        """Used in admin model to have a image preview."""
        if self.cover_image_id:
            return format_html(
                '<img src={} width="90" height="128">',
                get_image_url(self.cover_image_id, IGDBImageSize.COVER_SMALL_90_128),
            )
        return ""

    @property
    def average_score(self: Self) -> float:
        """Annotate the average score for the game."""
        if hasattr(self, "stats"):
            return float(self.stats.average_score)
        return 0.0

    @property
    def scores_count(self: Self) -> int:
        """Annotate the number of all ratings for the game."""
        if hasattr(self, "stats"):
            return self.stats.score_count
        return 0

    @property
    def rank_position(self: Self) -> int:
        """Annotate the rank position of the game. The rank position is calculated based on the average score."""
        if hasattr(self, "stats") and self.stats.rank_position is not None:
            return self.stats.rank_position
        return 0

    @property
    def members_count(self: Self) -> int:
        """Annotate the number of all members for the game."""
        if hasattr(self, "stats"):
            return self.stats.members_count
        return 0

    @property
    def popularity(self: Self) -> int:
        """Annotate the popularity of the game. The popularity is calculated based on the number of members."""
        if hasattr(self, "stats") and self.stats.popularity is not None:
            return self.stats.popularity
        return 0
