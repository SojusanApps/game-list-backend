"""This module contains the serializers for the game related data."""

from typing import Any, Self

from rest_framework import serializers

from my_game_list.games.models import (
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
    TranslationSuggestion,
    TranslationSuggestionField,
)
from my_game_list.moderation.masking import mask_if_moderated
from my_game_list.my_game_list.serializers import BaseDictionarySerializer
from my_game_list.users.models import User
from my_game_list.users.serializers import UserSerializer, UserSimpleSerializer


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


class CompanySerializer(BaseDictionarySerializer):
    """A serializer for the Company model."""

    class Meta(BaseDictionarySerializer.Meta):
        """Meta data for Company serializer."""

        model = Company
        fields = (
            *BaseDictionarySerializer.Meta.fields,
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
    """A serializer for the game follow model."""

    class Meta:
        """Meta data for game follow serializer."""

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
        fields = ("id", "score", "recommendation", "created_at", "review", "game", "user")

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

    user = serializers.SlugRelatedField(
        queryset=User.objects.all(),
        slug_field="id",
    )

    class Meta:
        """Meta data for the game review create serializer."""

        model = GameReview
        fields = ("id", "created_at", "review", "recommendation", "game", "user")


class GenreSerializer(BaseDictionarySerializer):
    """A serializer for genre model."""

    class Meta(BaseDictionarySerializer.Meta):
        """Meta data for a genre serializer."""

        model = Genre
        fields = (*BaseDictionarySerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class PlatformSerializer(BaseDictionarySerializer):
    """A serializer for the platform model."""

    class Meta(BaseDictionarySerializer.Meta):
        """Meta data for the platform serializer."""

        model = Platform
        fields = (*BaseDictionarySerializer.Meta.fields, "abbreviation", "igdb_id", "igdb_updated_at")


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


class GameEngineSerializer(BaseDictionarySerializer):
    """A serializer for the game engine model."""

    class Meta(BaseDictionarySerializer.Meta):
        """Meta data for the game engine serializer."""

        model = GameEngine
        fields = (*BaseDictionarySerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class GameModeSerializer(BaseDictionarySerializer):
    """A serializer for the game mode model."""

    class Meta(BaseDictionarySerializer.Meta):
        """Meta data for the game mode serializer."""

        model = GameMode
        fields = (*BaseDictionarySerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class PlayerPerspectiveSerializer(BaseDictionarySerializer):
    """A serializer for the player perspective model."""

    class Meta(BaseDictionarySerializer.Meta):
        """Meta data for the player perspective serializer."""

        model = PlayerPerspective
        fields = (*BaseDictionarySerializer.Meta.fields, "igdb_id", "igdb_updated_at")


class ExternalGameSourceSerializer(BaseDictionarySerializer):
    """A serializer for the external game source model."""

    class Meta(BaseDictionarySerializer.Meta):
        """Meta data for the external game source serializer."""

        model = ExternalGameSource
        fields = (*BaseDictionarySerializer.Meta.fields, "igdb_id", "igdb_updated_at")


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


class SteamImportNotFoundSerializer(serializers.Serializer[Any]):
    """A serializer for the Steam games that were not found in the database."""

    appid = serializers.IntegerField(help_text="The AppID of the Steam game.")
    name = serializers.CharField(help_text="The name of the Steam game.")


class SteamImportResponseSerializer(serializers.Serializer[Any]):
    """A serializer for the Steam import endpoint response."""

    matched = GameSimpleListSerializer(many=True, help_text="List of matched games found in the database.")
    not_found = SteamImportNotFoundSerializer(many=True, help_text="List of games not found in the database.")
    total_imported = serializers.IntegerField(help_text="Total number of games retrieved from Steam before filtration.")


class TitleImportRequestSerializer(serializers.Serializer[Any]):
    """A serializer for the title import endpoint request body."""

    titles = serializers.ListField(
        child=serializers.CharField(max_length=255, help_text="A game title to match."),
        min_length=1,
        max_length=10,
        help_text="Game titles to match against the catalogue, at most 10 per request.",
    )


class TitleImportMatchSerializer(serializers.Serializer[Any]):
    """A serializer for a single candidate game matched to an imported title."""

    id = serializers.IntegerField(help_text="The ID of the matched game.")
    title = serializers.CharField(help_text="The title of the matched game.")
    cover_image_id = serializers.CharField(help_text="The IGDB cover image ID of the matched game.")
    already_in_list = serializers.BooleanField(
        help_text="Whether the matched game is already on the requesting user's game list.",
    )


class TitleImportResultSerializer(serializers.Serializer[Any]):
    """A serializer for the match candidates of a single imported title."""

    title = serializers.CharField(help_text="The input title, echoed back verbatim.")
    matches = TitleImportMatchSerializer(
        many=True,
        help_text="Up to three candidate games, best match first; empty when nothing matched well enough.",
    )


class TitleImportResponseSerializer(serializers.Serializer[Any]):
    """A serializer for the title import endpoint response."""

    results = TitleImportResultSerializer(
        many=True,
        help_text="One entry per input title, in input order.",
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
            message = f"Ensure this field has no more than {max_length} characters."
            raise serializers.ValidationError({"proposed_value": message})

        request = self.context["request"]
        if TranslationSuggestion.objects.filter(
            game=attrs["game"],
            field=field,
            submitted_by=request.user,
            status=TranslationSuggestion.Status.PENDING,
        ).exists():
            message = "You already have a pending suggestion for this game and field."
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
