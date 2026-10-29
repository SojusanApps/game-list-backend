"""This module contains the serializers for the game related data."""

from typing import TYPE_CHECKING, Any, ClassVar, Self

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from game_list.game_list.serializers import BaseLookupSerializer
from game_list.games.models import (
    Company,
    ExternalGame,
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
    StoreMapping,
    StorePlatform,
    TranslationSuggestion,
    TranslationSuggestionField,
)
from game_list.moderation.masking import mask_if_moderated
from game_list.users.serializers import UserSerializer, UserSimpleSerializer

if TYPE_CHECKING:
    from game_list.users.models import User


class CompanySimpleNameSerializer(serializers.ModelSerializer[Company]):
    """A simple serializer for the Company model."""

    class Meta:
        """Meta data for simple Company serializer."""

        model = Company
        fields = ("id", "name")


class CompanyGameSerializer(serializers.ModelSerializer[Game]):
    """A serializer for the game model in company view."""

    class Meta:
        """Meta data for company game serializer."""

        model = Game
        fields = ("id", "cover_image_id", "title", "slug")


class CompanySerializer(BaseLookupSerializer):
    """A serializer for the Company model."""

    class Meta(BaseLookupSerializer.Meta):
        """Meta data for Company serializer."""

        model = Company
        fields = (
            *BaseLookupSerializer.Meta.fields,
            "company_logo_id",
            "igdb_id",
            "igdb_updated_at",
            "slug",
        )


class CompanyDetailSerializer(CompanySerializer):
    """A detailed serializer for the Company model."""

    games_published = CompanyGameSerializer(many=True, read_only=True)
    games_developed = CompanyGameSerializer(many=True, read_only=True)

    class Meta(CompanySerializer.Meta):
        """Meta data for Company detail serializer."""

        model = Company
        fields = (
            *CompanySerializer.Meta.fields,
            "games_published",
            "games_developed",
        )


class GameFollowSerializer(serializers.ModelSerializer[GameFollow]):
    """A serializer for reading the game follow model (list/retrieve)."""

    class Meta:
        """Meta data for game follow serializer."""

        model = GameFollow
        fields = ("id", "created_at", "game", "user")


class GameFollowCreateSerializer(serializers.ModelSerializer[GameFollow]):
    """A serializer for creating the game follow model."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        """Meta data for the game follow create serializer."""

        model = GameFollow
        fields = ("id", "created_at", "game", "user")


class GameMediaSerializer(serializers.ModelSerializer[GameMedia]):
    """A serializer for the game media model."""

    class Meta:
        """Meta data for the game media serializer."""

        model = GameMedia
        fields = ("id", "name")


class GameListSerializer(serializers.ModelSerializer[GameList]):
    """A serializer for the game list model."""

    status = serializers.CharField(source="get_status_display", read_only=True)
    status_code = serializers.CharField(source="status")
    game_id = serializers.IntegerField(source="game.id", read_only=True)
    game_slug = serializers.CharField(source="game.slug", read_only=True)
    title = serializers.CharField(source="game.title", read_only=True)
    game_cover_image = serializers.CharField(source="game.cover_image_id", read_only=True)
    owned_on = GameMediaSerializer(many=True)
    description = serializers.SerializerMethodField()

    class Meta:
        """Meta data for the game list serializer."""

        model = GameList
        fields = (
            "id",
            "status",
            "status_code",
            "score",
            "description",
            "completed_at",
            "started_at",
            "playtime",
            "created_at",
            "last_modified_at",
            "game_id",
            "game_slug",
            "title",
            "game_cover_image",
            "user",
            "owned_on",
        )

    def get_description(self: Self, instance: GameList) -> str:
        """Mask the note text for other viewers if it's moderated or its author is banned."""
        viewer: User = self.context["request"].user
        return mask_if_moderated(
            instance.description,
            moderated=instance.is_moderated or instance.user.is_banned,
            owner=instance.user,
            viewer=viewer,
        )


class GameListCreateSerializer(serializers.ModelSerializer[GameList]):
    """A serializer for the game list create model."""

    owned_on = serializers.SlugRelatedField(  # type: ignore[var-annotated]
        queryset=GameMedia.objects.all(),
        slug_field="id",
        many=True,
    )
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        """Meta data for the game list create serializer."""

        model = GameList
        fields = (
            "id",
            "status",
            "score",
            "description",
            "completed_at",
            "started_at",
            "playtime",
            "created_at",
            "last_modified_at",
            "game",
            "user",
            "owned_on",
        )


class GameListCompareRowSerializer(serializers.Serializer[Any]):
    """A serializer for a single row of a GameList comparison between two users."""

    game_id = serializers.IntegerField(help_text="The ID of the compared game.")
    game_slug = serializers.CharField(help_text="The slug of the compared game.")
    title = serializers.CharField(help_text="The title of the compared game.")
    game_cover_image = serializers.CharField(allow_null=True, help_text="The cover image ID of the compared game.")
    first_user_score = serializers.IntegerField(allow_null=True, help_text="The first user's score, if any.")
    first_user_status = serializers.CharField(allow_null=True, help_text="The first user's status, human-readable.")
    first_user_status_code = serializers.CharField(allow_null=True, help_text="The first user's raw status code.")
    second_user_score = serializers.IntegerField(allow_null=True, help_text="The second user's score, if any.")
    second_user_status = serializers.CharField(allow_null=True, help_text="The second user's status, human-readable.")
    second_user_status_code = serializers.CharField(allow_null=True, help_text="The second user's raw status code.")


class GameListCompareResponseSerializer(serializers.Serializer[Any]):
    """A serializer for the GameList compare endpoint response."""

    common = GameListCompareRowSerializer(many=True, help_text="Games both users have.")
    first_user_unique = GameListCompareRowSerializer(many=True, help_text="Games only the first user has.")
    second_user_unique = GameListCompareRowSerializer(many=True, help_text="Games only the second user has.")


class GameReviewSerializer(serializers.ModelSerializer[GameReview]):
    """A serializer for the game review model."""

    user = UserSerializer()
    score = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()

    class Meta:
        """Meta data for the game review serializer."""

        model = GameReview
        fields = ("id", "score", "recommendation", "language", "created_at", "review", "game", "user")

    def get_score(self: Self, instance: GameReview) -> int | None:
        """Get user score for the this game."""
        game_list_instance = instance.user.game_lists.filter(game__id=instance.game.id).first()
        if game_list_instance:
            return game_list_instance.score
        return None

    def get_review(self: Self, instance: GameReview) -> str:
        """Mask the review text for other viewers if it's moderated or its author is banned."""
        viewer: User = self.context["request"].user
        return mask_if_moderated(
            instance.review,
            moderated=instance.is_moderated or instance.user.is_banned,
            owner=instance.user,
            viewer=viewer,
        )


class GameReviewCreateSerializer(serializers.ModelSerializer[GameReview]):
    """A serializer for creating the game review model."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        """Meta data for the game review create serializer."""

        model = GameReview
        fields = ("id", "created_at", "review", "recommendation", "language", "game", "user")


class GenreSerializer(BaseLookupSerializer):
    """A serializer for genre model."""

    class Meta(BaseLookupSerializer.Meta):
        """Meta data for a genre serializer."""

        model = Genre
        fields = (*BaseLookupSerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class PlatformSerializer(BaseLookupSerializer):
    """A serializer for the platform model."""

    class Meta(BaseLookupSerializer.Meta):
        """Meta data for the platform serializer."""

        model = Platform
        fields = (*BaseLookupSerializer.Meta.fields, "abbreviation", "igdb_id", "igdb_updated_at")


class GameTypeSerializer(serializers.ModelSerializer[GameType]):
    """A serializer for the game type model."""

    class Meta:
        """Meta data for the game type serializer."""

        model = GameType
        fields = ("id", "type", "igdb_id", "igdb_updated_at")


class GameStatusSerializer(serializers.ModelSerializer[GameStatus]):
    """A serializer for the game status model."""

    class Meta:
        """Meta data for the game status serializer."""

        model = GameStatus
        fields = ("id", "status", "igdb_id", "igdb_updated_at")


class GameEngineSerializer(BaseLookupSerializer):
    """A serializer for the game engine model."""

    class Meta(BaseLookupSerializer.Meta):
        """Meta data for the game engine serializer."""

        model = GameEngine
        fields = (*BaseLookupSerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class GameModeSerializer(BaseLookupSerializer):
    """A serializer for the game mode model."""

    class Meta(BaseLookupSerializer.Meta):
        """Meta data for the game mode serializer."""

        model = GameMode
        fields = (*BaseLookupSerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class PlayerPerspectiveSerializer(BaseLookupSerializer):
    """A serializer for the player perspective model."""

    class Meta(BaseLookupSerializer.Meta):
        """Meta data for the player perspective serializer."""

        model = PlayerPerspective
        fields = (*BaseLookupSerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class ExternalGameSourceSerializer(BaseLookupSerializer):
    """A serializer for the external game source model."""

    class Meta(BaseLookupSerializer.Meta):
        """Meta data for the external game source serializer."""

        model = ExternalGameSource
        fields = (*BaseLookupSerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class ExternalGameSerializer(serializers.ModelSerializer[ExternalGame]):
    """A serializer for the external game model."""

    external_game_source = serializers.CharField(source="external_game_source.name", read_only=True)

    class Meta:
        """Meta data for the external game serializer."""

        model = ExternalGame
        fields = (
            "id",
            "external_game_source",
            "external_id",
            "url",
            "igdb_id",
            "igdb_updated_at",
        )


class GameSimpleListSerializer(serializers.ModelSerializer[Game]):
    """A lightweight serializer for the game model list view."""

    game_status: serializers.SlugRelatedField[GameStatus] = serializers.SlugRelatedField(
        read_only=True,
        slug_field="status",
    )
    game_type: serializers.SlugRelatedField[GameType] = serializers.SlugRelatedField(read_only=True, slug_field="type")

    class Meta:
        """Meta data for game list serializer."""

        model = Game
        fields = (
            "id",
            "title",
            "release_date",
            "created_at",
            "cover_image_id",
            "average_score",
            "scores_count",
            "rank_position",
            "members_count",
            "popularity",
            "game_status",
            "game_type",
            "slug",
        )


class GameSerializer(serializers.ModelSerializer[Game]):
    """A serializer for the game model."""

    publisher = CompanySerializer()
    developer = CompanySerializer()
    genres = GenreSerializer(many=True)
    platforms = PlatformSerializer(many=True)
    game_type = GameTypeSerializer()
    game_status = GameStatusSerializer()
    parent_game = CompanyGameSerializer()
    bundles = CompanyGameSerializer(many=True)
    dlcs = CompanyGameSerializer(many=True)
    expanded_games = CompanyGameSerializer(many=True)
    expansions = CompanyGameSerializer(many=True)
    forks = CompanyGameSerializer(many=True)
    ports = CompanyGameSerializer(many=True)
    standalone_expansions = CompanyGameSerializer(many=True)
    game_engines = GameEngineSerializer(many=True)
    game_modes = GameModeSerializer(many=True)
    player_perspectives = PlayerPerspectiveSerializer(many=True)
    external_games = ExternalGameSerializer(many=True)

    class Meta:
        """Meta data for game serializer."""

        model = Game
        fields = (
            "id",
            "title",
            "title_en",
            "created_at",
            "last_modified_at",
            "release_date",
            "cover_image_id",
            "summary",
            "publisher",
            "igdb_id",
            "igdb_updated_at",
            "developer",
            "genres",
            "platforms",
            "average_score",
            "scores_count",
            "rank_position",
            "members_count",
            "popularity",
            "game_type",
            "game_status",
            "parent_game",
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
            "external_games",
            "screenshots",
            "slug",
        )


class ReleaseCalendarQuerySerializer(serializers.Serializer[Any]):
    """A serializer for validating the query parameters for the release calendar endpoint."""

    start_date = serializers.DateField(
        required=True,
        help_text="Start date of the release date range (YYYY-MM-DD).",
    )
    end_date = serializers.DateField(
        required=True,
        help_text="End date of the release date range (YYYY-MM-DD). Must be at most 31 days after start_date.",
    )


TRANSLATION_SUGGESTION_FIELD_MAX_LENGTHS: dict[str, int] = {
    TranslationSuggestionField.TITLE: 255,
    TranslationSuggestionField.SUMMARY: 2000,
}


class GameReferenceSerializer(serializers.ModelSerializer[Game]):
    """A minimal reference to a game: id, title, slug, and cover image id."""

    class Meta:
        """Meta data for the game reference serializer."""

        model = Game
        fields = ("id", "title", "slug", "cover_image_id")


class TranslationSuggestionSerializer(serializers.ModelSerializer[TranslationSuggestion]):
    """A serializer for reading translation suggestions."""

    game = GameReferenceSerializer(read_only=True)
    submitted_by = UserSimpleSerializer(read_only=True)
    reviewed_by = UserSimpleSerializer(read_only=True)
    proposed_value = serializers.SerializerMethodField()

    class Meta:
        """Meta data for the translation suggestion serializer."""

        model = TranslationSuggestion
        fields = (
            "id",
            "game",
            "field",
            "submitted_by",
            "current_value",
            "proposed_value",
            "status",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
        )
        read_only_fields = tuple(f for f in fields if f != "proposed_value")

    def get_proposed_value(self: Self, instance: TranslationSuggestion) -> str:
        """Mask the proposed text for other viewers if it's moderated or its author is banned."""
        viewer: User = self.context["request"].user
        return mask_if_moderated(
            instance.proposed_value,
            moderated=instance.is_moderated or instance.submitted_by.is_banned,
            owner=instance.submitted_by,
            viewer=viewer,
        )


class TranslationSuggestionCreateSerializer(serializers.ModelSerializer[TranslationSuggestion]):
    """A serializer for submitting a new translation suggestion."""

    class Meta:
        """Meta data for the translation suggestion create serializer."""

        model = TranslationSuggestion
        fields = (
            "id",
            "game",
            "field",
            "proposed_value",
            "submitted_by",
            "current_value",
            "status",
            "submitted_at",
        )
        read_only_fields = ("id", "submitted_by", "current_value", "status", "submitted_at")

    def validate(self: Self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate that the proposed value fits within the target field's max length.

        Also validates that the requesting user does not already have a pending suggestion
        for the same game+field.
        """
        field: str = attrs["field"]
        max_length = TRANSLATION_SUGGESTION_FIELD_MAX_LENGTHS[field]
        proposed_value: str = attrs.get("proposed_value", "")
        if len(proposed_value) > max_length:
            proposed_value_message = _("Ensure this field has no more than %(max_length)s characters.") % {
                "max_length": max_length,
            }
            raise serializers.ValidationError({"proposed_value": proposed_value_message})

        request = self.context["request"]
        if TranslationSuggestion.objects.filter(
            game=attrs["game"],
            field=field,
            submitted_by=request.user,
            status=TranslationSuggestion.Status.PENDING,
        ).exists():
            message = _("You already have a pending suggestion for this game and field.")
            raise serializers.ValidationError({"non_field_errors": [message]})

        return attrs

    def create(self: Self, validated_data: dict[str, Any]) -> TranslationSuggestion:
        """Create a translation suggestion, snapshotting the game's current value server-side."""
        request = self.context["request"]
        game: Game = validated_data["game"]
        field: str = validated_data["field"]
        current_value = getattr(game, f"{field}_pl") or ""
        return TranslationSuggestion.objects.create(
            game=game,
            field=field,
            proposed_value=validated_data["proposed_value"],
            submitted_by=request.user,
            current_value=current_value,
        )


MAX_STORE_IMPORT_ENTRIES = 5000
PLATFORM_HELP_TEXT = "The store the game is listed on."
STORE_ID_HELP_TEXT = "The store's own identifier of the game."


class StoreEntrySerializer(serializers.Serializer[Any]):
    """A serializer for one game of a store library, as sent by the browser extension."""

    platform = serializers.ChoiceField(choices=StorePlatform.choices, help_text=PLATFORM_HELP_TEXT)
    store_id = serializers.CharField(max_length=255, help_text=STORE_ID_HELP_TEXT)
    title = serializers.CharField(max_length=255, help_text="The game's title on the store.")
    wishlisted = serializers.BooleanField(
        help_text="Whether the game is only on the store wishlist; false when the user owns it.",
    )


class StoreImportRequestSerializer(serializers.Serializer[Any]):
    """A serializer for the store import endpoint request body."""

    entries = StoreEntrySerializer(
        many=True,
        allow_empty=False,
        help_text=f"Store library entries to import, at most {MAX_STORE_IMPORT_ENTRIES} per request.",
    )

    def validate_entries(self: Self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reject a request with more entries than one request may carry."""
        if len(value) > MAX_STORE_IMPORT_ENTRIES:
            message = _("Ensure this field has no more than %(max)s entries.") % {"max": MAX_STORE_IMPORT_ENTRIES}
            raise serializers.ValidationError(message)
        return value


class StoreImportedGameSerializer(serializers.Serializer[Any]):
    """A serializer for a store entry that matched a game."""

    platform = serializers.CharField(help_text=PLATFORM_HELP_TEXT)
    store_id = serializers.CharField(help_text=STORE_ID_HELP_TEXT)
    game = GameReferenceSerializer(help_text="The game the entry was matched to.")


class StoreImportResponseSerializer(serializers.Serializer[Any]):
    """A serializer for the store import endpoint response."""

    imported = StoreImportedGameSerializer(many=True, help_text="Entries matched and added to the game list now.")
    already_added = StoreImportedGameSerializer(
        many=True,
        help_text="Entries matched to a game that was already on the game list.",
    )
    unmatched = StoreEntrySerializer(
        many=True,
        help_text="Entries that could not be matched and need the title match step.",
    )
    skipped = StoreEntrySerializer(
        many=True,
        help_text="Entries a Store Mapping marks as not a game; they are not imported.",
    )


class StoreMappingRefSerializer(serializers.Serializer[Any]):
    """The store reference an item of the bulk-create request may carry to propose a Store Mapping."""

    platform = serializers.ChoiceField(choices=StorePlatform.choices, help_text=PLATFORM_HELP_TEXT)
    store_id = serializers.CharField(max_length=255, help_text=STORE_ID_HELP_TEXT)
    store_title = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
        help_text="The game's title on the store.",
    )


class StoreLinkItemSerializer(StoreEntrySerializer):
    """A store entry matched by hand to a game that is already on the user's game list."""

    game = serializers.PrimaryKeyRelatedField(  # type: ignore[var-annotated]
        queryset=Game.objects.all(),
        help_text="The game on the user's list the entry was matched to.",
    )


class StoreLinkRequestSerializer(serializers.Serializer[Any]):
    """A serializer for the store link endpoint request body."""

    entries = StoreLinkItemSerializer(many=True, allow_empty=False, help_text="Matches to apply.")


class StoreNotAGameRequestSerializer(serializers.Serializer[Any]):
    """A serializer for the request proposing store items as not a game."""

    entries = StoreMappingRefSerializer(
        many=True,
        allow_empty=False,
        help_text="Store items the user marks as not a game (a soundtrack, for example).",
    )


class StoreMappingSerializer(serializers.ModelSerializer[StoreMapping]):
    """A serializer for reading store mappings."""

    game = GameReferenceSerializer(read_only=True, allow_null=True)
    submitted_by = UserSimpleSerializer(read_only=True)
    reviewed_by = UserSimpleSerializer(read_only=True)

    class Meta:
        """Meta data for the store mapping serializer."""

        model = StoreMapping
        fields = (
            "id",
            "platform",
            "store_id",
            "store_title",
            "game",
            "not_a_game",
            "submitted_by",
            "status",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
        )
        read_only_fields = fields


class StoreMappingCreateSerializer(serializers.ModelSerializer[StoreMapping]):
    """A serializer for an admin creating an already accepted store mapping by hand."""

    class Meta:
        """Meta data for the store mapping create serializer."""

        model = StoreMapping
        fields = ("id", "platform", "store_id", "store_title", "game", "not_a_game", "status")
        read_only_fields = ("id", "status")
        extra_kwargs: ClassVar[dict[str, dict[str, Any]]] = {
            "store_title": {"required": False},
            "game": {"required": False, "allow_null": True},
        }

    def validate(self: Self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Require a game unless the store item is marked as not a game, and forbid both."""
        if attrs.get("not_a_game") and attrs.get("game") is not None:
            message = _("A store item marked as not a game cannot be mapped to a game.")
            raise serializers.ValidationError(message)
        if not attrs.get("not_a_game") and attrs.get("game") is None:
            message = _("Choose a game, or mark the store item as not a game.")
            raise serializers.ValidationError({"game": message})
        return attrs


class StoreMappingRejectSerializer(serializers.Serializer[Any]):
    """A serializer for the optional reason an admin gives when rejecting a store mapping."""

    rejection_reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional reason for the rejection.",
    )


class GameListBulkCreateItemSerializer(GameListCreateSerializer):
    """The schema of one item of the bulk-create request: a game-list entry plus optional store references."""

    store_refs = StoreMappingRefSerializer(
        many=True,
        required=False,
        help_text="Store ids this game was picked for; each is recorded as a pending Store Mapping for the user.",
    )

    class Meta(GameListCreateSerializer.Meta):
        """Meta data for the game list bulk create item serializer."""

        fields = (*GameListCreateSerializer.Meta.fields, "store_refs")  # type: ignore[assignment]
