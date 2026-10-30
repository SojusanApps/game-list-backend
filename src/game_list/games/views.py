"""This module contains the viewsets for the game related data."""

from typing import TYPE_CHECKING, Any, Self, cast

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet

from game_list.game_list.permissions import IsAdminOrReadOnly, IsOwner
from game_list.games.filters import (
    CompanyFilterSet,
    ExternalGameSourceFilterSet,
    GameEngineFilterSet,
    GameFilterSet,
    GameFollowFilterSet,
    GameListFilterSet,
    GameMediaFilterSet,
    GameModeFilterSet,
    GameReviewFilterSet,
    GameStatusFilterSet,
    GameTypeFilterSet,
    GenreFilterSet,
    PlatformFilterSet,
    PlayerPerspectiveFilterSet,
    StoreMappingFilterSet,
    TranslationSuggestionFilterSet,
)
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
    StoreMapping,
    TranslationSuggestion,
)
from game_list.games.permissions import IsSuggestionSubmitter
from game_list.games.serializers import (
    CompanyDetailSerializer,
    CompanySerializer,
    ExternalGameSourceSerializer,
    GameEngineSerializer,
    GameFollowCreateSerializer,
    GameFollowSerializer,
    GameListBulkCreateItemSerializer,
    GameListCompareResponseSerializer,
    GameListCreateSerializer,
    GameListSerializer,
    GameMediaSerializer,
    GameModeSerializer,
    GameReviewCreateSerializer,
    GameReviewSerializer,
    GameSerializer,
    GameSimpleListSerializer,
    GameStatusSerializer,
    GameTypeSerializer,
    GenreSerializer,
    PlatformSerializer,
    PlayerPerspectiveSerializer,
    ReleaseCalendarQuerySerializer,
    StoreImportRequestSerializer,
    StoreImportResponseSerializer,
    StoreLinkRequestSerializer,
    StoreMappingCreateSerializer,
    StoreMappingRefSerializer,
    StoreMappingRejectSerializer,
    StoreMappingSerializer,
    StoreNotAGameRequestSerializer,
    TranslationSuggestionCreateSerializer,
    TranslationSuggestionSerializer,
)
from game_list.games.store_import import (
    StoreEntry,
    StoreLink,
    accept_mapping,
    create_accepted_mapping,
    import_entries,
    link_listed_games,
    submit_pending_mapping,
)
from game_list.notifications.constants import NotificationCategory, NotificationVerb
from game_list.notifications.utils import notify_send
from game_list.users.models import User

if TYPE_CHECKING:
    import datetime as dt

    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.utils.serializer_helpers import ReturnDict


HIGHEST_NUMBER_OF_DAYS_IN_MONTH = 31
MAX_GAMES_PER_DAY_IN_CALENDAR = 3


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all companies in the catalogue. "
            "Companies are read-only Lookup Model entries that represent both publishers "
            "and developers. Filter by name (bilingual EN/PL partial match) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact company ID.",
            ),
            OpenApiParameter(
                name="name",
                description=(
                    "Filter by company name. Searches both the English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the company's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description=(
            "Retrieve a single company by ID. "
            "The detail response includes the lists of games the company has published and developed."
        ),
    ),
)
class CompanyViewSet(ReadOnlyModelViewSet[Company]):
    """A ViewSet for the Company model."""

    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = CompanyFilterSet

    def get_queryset(self: Self) -> QuerySet[Company]:
        """Get the queryset for the Company model."""
        queryset = super().get_queryset()
        if self.action == "retrieve":
            return queryset.prefetch_related("games_published", "games_developed")
        return queryset

    def get_serializer_class(
        self: Self,
    ) -> type[CompanySerializer | CompanyDetailSerializer]:
        """Get the serializer class for the Company model."""
        return CompanyDetailSerializer if self.action == "retrieve" else CompanySerializer


@extend_schema_view(
    list=extend_schema(
        description=(
            "List game-follow records. "
            "A game follow records that a user is tracking a game to receive updates. "
            "Filter by game or user ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game-follow record ID.",
            ),
            OpenApiParameter(
                name="game",
                description="Filter by game ID.",
            ),
            OpenApiParameter(
                name="user",
                description="Filter by user ID.",
            ),
        ],
    ),
    create=extend_schema(
        description="Follow a game. Creates a record linking the authenticated user to the specified game.",
    ),
    retrieve=extend_schema(
        description="Retrieve a single game-follow record by ID.",
    ),
    destroy=extend_schema(
        description="Unfollow a game. Removes the follow record permanently.",
    ),
)
class GameFollowViewSet(
    CreateModelMixin,
    RetrieveModelMixin,
    ListModelMixin,
    DestroyModelMixin,
    GenericViewSet[GameFollow],
):
    """A ViewSet for the GameFollow model.

    No update/partial_update: a follow has no mutable attribute once created, so the only
    meaningful operations are follow (create) and unfollow (destroy).
    """

    queryset = GameFollow.objects.all()
    permission_classes = (IsAuthenticated, IsOwner)
    filterset_class = GameFollowFilterSet

    def get_serializer_class(self: Self) -> type[GameFollowCreateSerializer | GameFollowSerializer]:
        """Get the serializer class for the GameFollow model."""
        return GameFollowCreateSerializer if self.action == "create" else GameFollowSerializer

    def get_queryset(self: Self) -> QuerySet[GameFollow]:
        """Restrict list/retrieve to the requesting user's own follows."""
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        return queryset.filter(user=user)


@extend_schema_view(
    list=extend_schema(
        description=(
            "List game-list entries. Open to anonymous visitors as well as authenticated users. "
            "Each entry tracks a user's relationship to a game including the play status "
            "(e.g. Playing, Completed, Plan to Play). "
            "Filter by status, game ID, user ID, or any game attribute. "
            "Entries can be ordered by the owner's score or by game title using the `ordering` parameter."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game-list entry ID.",
            ),
            OpenApiParameter(
                name="status",
                description="Filter by play status. Can be specified multiple times to match several statuses.",
            ),
            OpenApiParameter(
                name="game",
                description="Filter by game ID.",
            ),
            OpenApiParameter(
                name="user",
                description="Filter by user ID.",
            ),
            OpenApiParameter(
                name="title",
                description="Filter by game title using fuzzy trigram similarity (supports typos and partial matches).",
            ),
            OpenApiParameter(
                name="release_date_after",
                description="Filter games released on or after this date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="release_date_before",
                description="Filter games released on or before this date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="publisher",
                description="Filter by publisher name (English or Polish, case-insensitive substring match).",
            ),
            OpenApiParameter(
                name="developer",
                description="Filter by developer name (English or Polish, case-insensitive substring match).",
            ),
            OpenApiParameter(
                name="genres",
                description="Filter by genre name (English or Polish). Can be specified multiple times.",
                many=True,
            ),
            OpenApiParameter(
                name="platforms",
                description="Filter by platform name (English or Polish). Can be specified multiple times.",
                many=True,
            ),
            OpenApiParameter(
                name="game_type",
                description="Filter by game type (English or Polish). Can be specified multiple times.",
                many=True,
            ),
            OpenApiParameter(
                name="game_status",
                description="Filter by game release status (English or Polish). Can be specified multiple times.",
                many=True,
            ),
            OpenApiParameter(
                name="game_engines",
                description="Filter by game engine name (English or Polish). Can be specified multiple times.",
                many=True,
            ),
            OpenApiParameter(
                name="game_modes",
                description="Filter by game mode (English or Polish). Can be specified multiple times.",
                many=True,
            ),
            OpenApiParameter(
                name="player_perspectives",
                description="Filter by player perspective (English or Polish). Can be specified multiple times.",
                many=True,
            ),
            OpenApiParameter(
                name="external_games",
                description="Filter by external game source (English or Polish). Can be specified multiple times.",
                many=True,
            ),
            OpenApiParameter(
                name="ordering",
                description=(
                    "Order results by the owner's score or by game title (in the requested language, "
                    "falling back to English). "
                    "Accepted values: score, -score, title, -title. Prefix with '-' for descending. "
                    "Several values can be combined with commas, e.g. `-score,title`. "
                    "Unscored entries always come last when ordering by score. "
                    "Ties are ordered by game title A-Z (unless title is already requested), then by ID. "
                    "An explicit ordering replaces the best-match-first order of the `title` filter."
                ),
            ),
        ],
    ),
    create=extend_schema(
        description="Add a game to the authenticated user's game list with the specified play status.",
    ),
    retrieve=extend_schema(
        description="Retrieve a single game-list entry by ID.",
    ),
    update=extend_schema(
        description="Replace all fields of a game-list entry.",
    ),
    partial_update=extend_schema(
        description="Update one or more fields of a game-list entry, for example to change the play status.",
    ),
    destroy=extend_schema(
        description="Remove a game-list entry. This does not delete the underlying game record.",
    ),
)
class GameListViewSet(ModelViewSet[GameList]):
    """A ViewSet for the GameList model."""

    queryset = GameList.objects.all()
    serializer_class = GameListSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, IsOwner)
    filterset_class = GameListFilterSet

    def get_serializer_class(
        self: Self,
    ) -> type[GameListCreateSerializer | GameListSerializer]:
        """Get the serializer class for the Game model."""
        return (
            GameListCreateSerializer
            if self.action
            in [
                "create",
                "update",
                "partial_update",
            ]
            else GameListSerializer
        )

    @extend_schema(
        description=(
            "Return a random game from the authenticated user's game list that has status "
            "Plan to Play. Returns HTTP 404 if the user has no Plan to Play games. "
            "Use this endpoint to get a suggestion for what to play next."
        ),
    )
    @action(detail=False, methods=["get"], url_path="random-ptp")
    def random_ptp(self: Self, request: Request) -> Response:
        """Return a random game from the user's game list in status Plan To Play."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        ptp_game = (
            self.get_queryset()
            .filter(user_id=request.user.pk, status=GameListStatus.PLAN_TO_PLAY)
            .order_by("?")
            .first()
        )
        if not ptp_game:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(ptp_game)
        return Response(serializer.data)

    @extend_schema(
        description=(
            "Import a store library read by the browser extension (Platform Sync). Each entry is matched by its "
            "store id: first against IGDB's external games, then against accepted Store Mappings, then against "
            "the user's own pending ones; an id that points at more than one game counts as unmatched. Matched "
            "games that are not on the authenticated user's game list are added as Plan to Play, unscored, with "
            "`owned_on` set to the store only for owned (not wishlisted) games. For a matched game already on the "
            "list nothing changes except that an owned game's store is appended to `owned_on`. Unmatched entries "
            "are returned so the client can run the title match step on them. Entries a Store Mapping marks as "
            "not a game are skipped and returned as `skipped`."
        ),
        request=StoreImportRequestSerializer,
        responses={200: StoreImportResponseSerializer},
    )
    @action(detail=False, methods=["post"], url_path="store-import", filter_backends=[], pagination_class=None)
    def store_import(self: Self, request: Request) -> Response:
        """Auto-import the entries of a store library that can be matched by store id."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        request_serializer = StoreImportRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        entries = [StoreEntry(**entry) for entry in request_serializer.validated_data["entries"]]

        with transaction.atomic():
            outcome = import_entries(entries, request.user)

        games = Game.objects.in_bulk({game_id for _, game_id in (*outcome.imported, *outcome.already_added)})
        serializer = StoreImportResponseSerializer(
            {
                "imported": [
                    {"platform": entry.platform, "store_id": entry.store_id, "game": games[game_id]}
                    for entry, game_id in outcome.imported
                ],
                "already_added": [
                    {"platform": entry.platform, "store_id": entry.store_id, "game": games[game_id]}
                    for entry, game_id in outcome.already_added
                ],
                "unmatched": [
                    {
                        "platform": entry.platform,
                        "store_id": entry.store_id,
                        "title": entry.title,
                        "wishlisted": entry.wishlisted,
                    }
                    for entry in outcome.unmatched
                ],
                "skipped": [
                    {
                        "platform": entry.platform,
                        "store_id": entry.store_id,
                        "title": entry.title,
                        "wishlisted": entry.wishlisted,
                    }
                    for entry in outcome.skipped
                ],
            },
        )
        return Response(serializer.data)

    @extend_schema(
        description=(
            "Match store entries by hand to games that are already on the authenticated user's game list. Each "
            "match is recorded as a pending Store Mapping of the user, and for an owned (not wishlisted) entry "
            "the store is appended to `owned_on`. Nothing else of the game list entry changes; a game that is "
            "not on the list is ignored."
        ),
        request=StoreLinkRequestSerializer,
        responses={204: None},
    )
    @action(detail=False, methods=["post"], url_path="store-link", filter_backends=[], pagination_class=None)
    def store_link(self: Self, request: Request) -> Response:
        """Link store entries to games the user already has."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        serializer = StoreLinkRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        links = [
            StoreLink(
                entry=StoreEntry(**{key: item[key] for key in ("platform", "store_id", "title", "wishlisted")}),
                game=item["game"],
            )
            for item in serializer.validated_data["entries"]
        ]
        with transaction.atomic():
            link_listed_games(links, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description=(
            "Propose store items as not a game (a soundtrack, for example). Each becomes a pending Store "
            "Mapping of the authenticated user: for them the store import skips the item at once, and for "
            "everyone once an admin accepts it. Items an accepted mapping already covers are ignored."
        ),
        request=StoreNotAGameRequestSerializer,
        responses={204: None},
    )
    @action(detail=False, methods=["post"], url_path="store-not-a-game", filter_backends=[], pagination_class=None)
    def store_not_a_game(self: Self, request: Request) -> Response:
        """Record the user's proposals that store items are not games."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        serializer = StoreNotAGameRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for item in serializer.validated_data["entries"]:
                submit_pending_mapping(
                    request.user,
                    (item["platform"], item["store_id"]),
                    item["store_title"],
                    None,
                )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description=(
            "Export the full game list of the authenticated user as JSON. "
            "Returns all entries without pagination. "
            "Use this endpoint to back up or transfer a user's complete game list."
        ),
        responses={200: GameListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="export", filter_backends=[], pagination_class=None)
    def export(self: Self, request: Request) -> Response:
        """Return the full game list of the authenticated user without pagination."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        queryset = self.get_queryset().filter(user_id=request.user.pk)
        serializer = GameListSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @extend_schema(
        description=(
            "Bulk-create game-list entries for the authenticated user. "
            "Accepts a list of objects each containing a game ID and play status. "
            "An item that came from store libraries may also carry `store_refs` (each with platform, store_id "
            "and store_title); the picked game is then recorded as a pending Store Mapping for the user "
            "for every one of them. "
            "Returns the list of created game-list entries. "
            "This endpoint is useful for bulk-adding games to the user's list."
        ),
        request=GameListBulkCreateItemSerializer(many=True),
        responses={201: GameListSerializer(many=True)},
    )
    @action(detail=False, methods=["post"], url_path="bulk-create", filter_backends=[], pagination_class=None)
    def bulk_create(self: Self, request: Request) -> Response:
        """Bulk-create GameList entries for the authenticated user."""
        items = request.data
        if not isinstance(items, list) or len(items) == 0:
            return Response({"non_field_errors": ["This field may not be empty."]}, status=status.HTTP_400_BAD_REQUEST)

        serializers_list = []
        store_refs: list[list[dict[str, Any]]] = []
        for item in items:
            data = {key: value for key, value in item.items() if key != "store_refs"}
            data["owned_on"] = item.get("owned_on", [])
            serializer = GameListCreateSerializer(data=data, context=self.get_serializer_context())
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            serializers_list.append(serializer)
            ref_serializer = StoreMappingRefSerializer(data=item.get("store_refs") or [], many=True)
            if not ref_serializer.is_valid():
                return Response({"store_refs": ref_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            store_refs.append([dict(ref) for ref in ref_serializer.validated_data])

        with transaction.atomic():
            instances = [s.save() for s in serializers_list]
            for instance, refs in zip(instances, store_refs, strict=True):
                for store_ref in refs:
                    submit_pending_mapping(
                        cast("User", request.user),
                        (store_ref["platform"], store_ref["store_id"]),
                        store_ref["store_title"],
                        instance.game,
                    )

        result = GameListSerializer(instances, many=True, context=self.get_serializer_context())
        return Response(result.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        description=(
            "Compare two users' game lists. Games are matched by Game, independent of each user's "
            "status — a Completed entry for one user and a Plan to Play entry for the other still "
            "count as a common game. Returns three groups: games both users have (with each user's "
            "score/status shown independently), games only the first user has, and games only the "
            "second user has. Each group is ordered alphabetically by title. "
            "Returns 400 if the two user IDs are the same, or 404 if either user does not exist."
        ),
        parameters=[
            OpenApiParameter(
                name="first_user_id",
                description="ID of the first user to compare.",
                required=True,
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
            ),
            OpenApiParameter(
                name="second_user_id",
                description="ID of the second user to compare.",
                required=True,
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
            ),
        ],
        responses={200: GameListCompareResponseSerializer},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"(?P<first_user_id>[^/.]+)/compare/(?P<second_user_id>[^/.]+)",
    )
    def compare(
        self: Self,
        request: Request,
        first_user_id: str,
        second_user_id: str,
    ) -> Response:
        """Compare two users' game lists, partitioned into common and unique games."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        if first_user_id == second_user_id:
            return Response(
                {"non_field_errors": ["Cannot compare a user with themselves."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_user = User.objects.filter(pk=first_user_id).first()
        second_user = User.objects.filter(pk=second_user_id).first()
        if first_user is None or second_user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        first_entries = {gl.game_id: gl for gl in GameList.objects.filter(user=first_user).select_related("game")}
        second_entries = {gl.game_id: gl for gl in GameList.objects.filter(user=second_user).select_related("game")}

        common_ids = first_entries.keys() & second_entries.keys()
        first_only_ids = first_entries.keys() - second_entries.keys()
        second_only_ids = second_entries.keys() - first_entries.keys()

        data = {
            "common": self._build_compare_rows(common_ids, first_entries, second_entries),
            "first_user_unique": self._build_compare_rows(first_only_ids, first_entries, second_entries),
            "second_user_unique": self._build_compare_rows(second_only_ids, first_entries, second_entries),
        }
        serializer = GameListCompareResponseSerializer(data)
        return Response(serializer.data)

    @staticmethod
    def _build_compare_rows(
        game_ids: set[int],
        first_entries: dict[int, GameList],
        second_entries: dict[int, GameList],
    ) -> list[dict[str, Any]]:
        """Build comparison rows for the given game IDs, sorted alphabetically by title."""
        rows = []
        for game_id in game_ids:
            first_entry = first_entries.get(game_id)
            second_entry = second_entries.get(game_id)
            entry = cast("GameList", first_entry or second_entry)
            game = entry.game
            rows.append(
                {
                    "game_id": game.id,
                    "game_slug": game.slug,
                    "title": game.title,
                    "game_cover_image": game.cover_image_id,
                    "first_user_score": first_entry.score if first_entry else None,
                    "first_user_status": first_entry.get_status_display() if first_entry else None,
                    "first_user_status_code": first_entry.status if first_entry else None,
                    "second_user_score": second_entry.score if second_entry else None,
                    "second_user_status": second_entry.get_status_display() if second_entry else None,
                    "second_user_status_code": second_entry.status if second_entry else None,
                },
            )
        return sorted(rows, key=lambda row: row["title"])


class GameReviewPagination(PageNumberPagination):
    """Paginates GameReview listings; documents the extra `recommendation_counts` field for the OpenAPI schema."""

    def get_paginated_response_schema(self: Self, schema: dict[str, Any]) -> dict[str, Any]:
        """Add `recommendation_counts` to the paginated response schema."""
        response_schema = super().get_paginated_response_schema(schema)
        response_schema["properties"]["recommendation_counts"] = {
            "type": "object",
            "nullable": True,
            "properties": {
                GameReviewRecommendation.RECOMMENDED.value: {"type": "integer"},
                GameReviewRecommendation.NOT_RECOMMENDED.value: {"type": "integer"},
                GameReviewRecommendation.UNDECIDED.value: {"type": "integer"},
            },
            "description": (
                "Count of reviews per recommendation for the game in the `game` filter, ignoring the "
                "`recommendation` filter itself; null when no `game` filter is given."
            ),
        }
        return response_schema


@extend_schema_view(
    list=extend_schema(
        description=(
            "List game reviews. "
            "Each review contains a numeric score, a recommendation, and an optional text body submitted "
            "by a user. Filter by score, recommendation, game ID, or reviewer user ID. "
            "When filtered by game ID, the response also includes a `recommendation_counts` breakdown "
            "(counts of Recommended / Not Recommended / Undecided across all that game's reviews, "
            "ignoring the `recommendation` filter itself); it is `null` when no game ID filter is given."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game review ID.",
            ),
            OpenApiParameter(
                name="score",
                description="Filter by exact review score.",
            ),
            OpenApiParameter(
                name="recommendation",
                description="Filter by recommendation (recommended, not_recommended, undecided).",
            ),
            OpenApiParameter(
                name="game",
                description="Filter by game ID.",
            ),
            OpenApiParameter(
                name="user",
                description="Filter by reviewer user ID.",
            ),
            OpenApiParameter(
                name="ordering",
                description=(
                    "Order results by field. "
                    "Accepted values: created_at, -created_at, score, -score. "
                    "Use `-created_at` for newest first and `-score` for the reviewer's highest score first. "
                    "Reviews whose author has not scored the game always come last when ordering by score. "
                    "Prefix with '-' for descending."
                ),
            ),
        ],
    ),
    create=extend_schema(
        description="Submit a review for a game. The authenticated user is recorded as the reviewer.",
    ),
    retrieve=extend_schema(
        description="Retrieve a single game review by ID.",
    ),
    update=extend_schema(
        description="Replace all fields of an existing game review.",
    ),
    partial_update=extend_schema(
        description="Update one or more fields of a game review, for example to revise the score or text.",
    ),
    destroy=extend_schema(
        description="Delete a game review permanently.",
    ),
)
class GameReviewViewSet(ModelViewSet[GameReview]):
    """A ViewSet for the GameReview model."""

    queryset = GameReview.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly, IsOwner)
    filterset_class = GameReviewFilterSet
    pagination_class = GameReviewPagination

    def get_serializer_class(
        self: Self,
    ) -> type[GameReviewCreateSerializer | GameReviewSerializer]:
        """Get the serializer class for the Game model."""
        return (
            GameReviewCreateSerializer
            if self.action
            in [
                "create",
                "update",
                "partial_update",
            ]
            else GameReviewSerializer
        )

    def list(self: Self, request: Request, *args: Any, **kwargs: Any) -> Response:  # noqa: ANN401
        """List game reviews, adding a per-game recommendation breakdown when filtered by game."""
        response = super().list(request, *args, **kwargs)
        response.data["recommendation_counts"] = self._get_recommendation_counts(request)
        return response

    def _get_recommendation_counts(self: Self, request: Request) -> dict[str, int] | None:
        """Count reviews per recommendation for the game in the `game` query param, ignoring other filters."""
        game_id_param = request.query_params.get("game")
        if game_id_param is None or not game_id_param.isdigit():
            return None

        counts: dict[str, int] = dict.fromkeys(GameReviewRecommendation.values, 0)
        rows = (
            GameReview.objects.filter(game_id=int(game_id_param)).values("recommendation").annotate(total=Count("id"))
        )
        for row in rows:
            counts[row["recommendation"]] = row["total"]

        return counts


@extend_schema_view(
    list=extend_schema(
        description=(
            "List translation suggestions. Every suggestion is visible to any authenticated user, "
            "regardless of who submitted it or its status (pending, accepted, rejected, withdrawn)."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact suggestion ID.",
            ),
            OpenApiParameter(
                name="game",
                description="Filter by the ID of the game the suggestion targets.",
            ),
            OpenApiParameter(
                name="field",
                description="Filter by the targeted Game field. Accepted values: title, summary.",
            ),
            OpenApiParameter(
                name="status",
                description="Filter by lifecycle status. Accepted values: pending, accepted, rejected, withdrawn.",
            ),
            OpenApiParameter(
                name="submitted_by",
                description="Filter by the ID of the user who submitted the suggestion.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single translation suggestion by ID.",
    ),
    create=extend_schema(
        description=(
            "Submit a new translation suggestion for a game's title or summary. "
            "The current value is snapshotted server-side from the live game field, "
            "and the suggestion is always created with pending status, attributed to the requesting user."
        ),
    ),
)
class TranslationSuggestionViewSet(
    GenericViewSet[TranslationSuggestion],
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
):
    """A ViewSet for submitting and browsing translation suggestions."""

    queryset = TranslationSuggestion.objects.all()
    permission_classes = (IsAuthenticated,)
    filterset_class = TranslationSuggestionFilterSet

    def get_serializer_class(
        self: Self,
    ) -> type[TranslationSuggestionCreateSerializer | TranslationSuggestionSerializer]:
        """Get the serializer class for the translation suggestion viewset."""
        return TranslationSuggestionCreateSerializer if self.action == "create" else TranslationSuggestionSerializer

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsSuggestionSubmitter],
    )
    def withdraw(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Withdraw a pending suggestion. Only the original submitter may call this."""
        suggestion = self.get_object()
        if suggestion.status != TranslationSuggestion.Status.PENDING:
            message = _("Only a pending suggestion can be withdrawn.")
            raise ValidationError(message)
        suggestion.status = TranslationSuggestion.Status.WITHDRAWN
        suggestion.save(update_fields=["status"])
        serializer = self.get_serializer(suggestion)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAdminUser],
    )
    def accept(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Accept a pending suggestion, applying it to the game and superseding sibling suggestions."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        suggestion = self.get_object()
        if suggestion.status != TranslationSuggestion.Status.PENDING:
            message = _("Only a pending suggestion can be accepted.")
            raise ValidationError(message)

        now = timezone.now()
        with transaction.atomic():
            game = suggestion.game
            setattr(game, f"{suggestion.field}_pl", suggestion.proposed_value)
            game.save()

            suggestion.status = TranslationSuggestion.Status.ACCEPTED
            suggestion.reviewed_by = request.user
            suggestion.reviewed_at = now
            suggestion.save(update_fields=["status", "reviewed_by", "reviewed_at"])

            TranslationSuggestion.objects.filter(
                game=game,
                field=suggestion.field,
                status=TranslationSuggestion.Status.PENDING,
            ).exclude(pk=suggestion.pk).update(
                status=TranslationSuggestion.Status.REJECTED,
                reviewed_by=request.user,
                reviewed_at=now,
            )

        notify_send(
            sender=request.user,
            recipient=suggestion.submitted_by,
            verb=NotificationVerb.TRANSLATION_SUGGESTION_ACCEPTED,
            target=suggestion,
            category=NotificationCategory.TRANSLATION_SUGGESTION,
        )

        serializer = self.get_serializer(suggestion)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAdminUser],
    )
    def reject(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Reject a pending suggestion, optionally with a reason. Never modifies the Game record."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        suggestion = self.get_object()
        if suggestion.status != TranslationSuggestion.Status.PENDING:
            message = _("Only a pending suggestion can be rejected.")
            raise ValidationError(message)

        rejection_reason = request.data.get("rejection_reason", "") if isinstance(request.data, dict) else ""
        suggestion.status = TranslationSuggestion.Status.REJECTED
        suggestion.reviewed_by = request.user
        suggestion.reviewed_at = timezone.now()
        suggestion.rejection_reason = rejection_reason
        suggestion.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])

        notify_send(
            sender=request.user,
            recipient=suggestion.submitted_by,
            verb=NotificationVerb.TRANSLATION_SUGGESTION_REJECTED,
            target=suggestion,
            category=NotificationCategory.TRANSLATION_SUGGESTION,
            description=rejection_reason,
        )

        serializer = self.get_serializer(suggestion)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        description=(
            "List store mappings (admin only), pending ones for review as well as accepted and rejected ones. "
            "Filter by status, platform, store id, game or submitter."
        ),
        parameters=[
            OpenApiParameter(name="id", description="Filter by exact store mapping ID."),
            OpenApiParameter(
                name="platform",
                description="Filter by store. Accepted values: steam, epic, gog, playstation, nintendo.",
            ),
            OpenApiParameter(name="store_id", description="Filter by the store's own identifier of the game."),
            OpenApiParameter(name="game", description="Filter by the ID of the game the store id is mapped to."),
            OpenApiParameter(
                name="status",
                description="Filter by lifecycle status. Accepted values: pending, accepted, rejected.",
            ),
            OpenApiParameter(
                name="submitted_by",
                description="Filter by the ID of the user who submitted the mapping.",
            ),
            OpenApiParameter(
                name="not_a_game",
                description="Filter mappings that mark a store item as not a game (true) or map it to a game (false).",
            ),
        ],
    ),
    retrieve=extend_schema(description="Retrieve a single store mapping (admin only)."),
    create=extend_schema(
        description=(
            "Create a store mapping by hand (admin only), to a game or marked `not_a_game` (a soundtrack, for "
            "example) so imports skip the store item. It is accepted at once and supersedes the store "
            "id's previous accepted mapping; other pending mappings for the same store id are rejected."
        ),
        request=StoreMappingCreateSerializer,
        responses={201: StoreMappingSerializer},
    ),
)
class StoreMappingViewSet(GenericViewSet[StoreMapping], ListModelMixin, RetrieveModelMixin):
    """A ViewSet for reviewing and creating store mappings."""

    queryset = StoreMapping.objects.select_related("game", "submitted_by", "reviewed_by")
    permission_classes = (IsAdminUser,)
    filterset_class = StoreMappingFilterSet

    def get_serializer_class(self: Self) -> type[StoreMappingCreateSerializer | StoreMappingSerializer]:
        """Get the serializer class for the store mapping viewset."""
        return StoreMappingCreateSerializer if self.action == "create" else StoreMappingSerializer

    def _serialize(self: Self, mapping: StoreMapping) -> ReturnDict[str, Any]:
        """Serialize a store mapping for a response."""
        return StoreMappingSerializer(mapping, context=self.get_serializer_context()).data

    def create(self: Self, request: Request) -> Response:
        """Create an accepted store mapping on behalf of the admin."""
        serializer = StoreMappingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mapping = create_accepted_mapping(
            cast("User", request.user),
            serializer.validated_data["platform"],
            serializer.validated_data["store_id"],
            serializer.validated_data.get("store_title", ""),
            serializer.validated_data.get("game"),
        )
        return Response(self._serialize(mapping), status=status.HTTP_201_CREATED)

    @extend_schema(
        description=(
            "Accept a pending store mapping, making it global. It supersedes the store id's previous "
            "accepted mapping and rejects the other pending mappings for the same store id. "
            "Game lists that already exist are not changed."
        ),
        request=None,
        responses={200: StoreMappingSerializer},
    )
    @action(detail=True, methods=["post"])
    def accept(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Accept a pending store mapping."""
        mapping = self.get_object()
        if mapping.status != StoreMapping.Status.PENDING:
            message = _("Only a pending mapping can be accepted.")
            raise ValidationError(message)
        accept_mapping(mapping, cast("User", request.user))
        return Response(self._serialize(mapping))

    @extend_schema(
        description=(
            "Reject a pending store mapping, optionally with a reason. The mapping stops applying to its "
            "submitter. Game lists that already exist are not changed."
        ),
        request=StoreMappingRejectSerializer,
        responses={200: StoreMappingSerializer},
    )
    @action(detail=True, methods=["post"])
    def reject(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Reject a pending store mapping."""
        mapping = self.get_object()
        if mapping.status != StoreMapping.Status.PENDING:
            message = _("Only a pending mapping can be rejected.")
            raise ValidationError(message)
        reason_serializer = StoreMappingRejectSerializer(data=request.data)
        reason_serializer.is_valid(raise_exception=True)
        mapping.status = StoreMapping.Status.REJECTED
        mapping.reviewed_by = cast("User", request.user)
        mapping.reviewed_at = timezone.now()
        mapping.rejection_reason = reason_serializer.validated_data["rejection_reason"]
        mapping.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])
        return Response(self._serialize(mapping))


@extend_schema_view(
    list=extend_schema(
        description=(
            "List games in the catalogue. "
            "The `title` filter searches across both the English (`title_en`) and Polish "
            "(`title_pl`) title fields simultaneously. "
            "Results can be ordered by `rank_position`, `popularity`, `release_date`, "
            "or `created_at` using the `ordering` parameter."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game ID.",
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the game's IGDB identifier.",
            ),
            OpenApiParameter(
                name="title",
                description=(
                    "Search by game title. Searches both the English and Polish title fields "
                    "simultaneously (case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="release_date_after",
                description="Filter games with a release date on or after this date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="release_date_before",
                description="Filter games with a release date on or before this date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="publisher",
                description=(
                    "Filter by publisher name. Searches both English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="developer",
                description=(
                    "Filter by developer name. Searches both English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="genres",
                description=(
                    "Filter by genre name. Accepts names in English or Polish. Can be specified multiple times."
                ),
            ),
            OpenApiParameter(
                name="platforms",
                description=(
                    "Filter by platform name. Accepts names in English or Polish. Can be specified multiple times."
                ),
            ),
            OpenApiParameter(
                name="game_type",
                description=(
                    "Filter by game type name. Accepts names in English or Polish. Can be specified multiple times."
                ),
            ),
            OpenApiParameter(
                name="game_status",
                description=(
                    "Filter by game status name. Accepts names in English or Polish. Can be specified multiple times."
                ),
            ),
            OpenApiParameter(
                name="game_engines",
                description=(
                    "Filter by game engine name. Accepts names in English or Polish. Can be specified multiple times."
                ),
            ),
            OpenApiParameter(
                name="game_modes",
                description=(
                    "Filter by game mode name. Accepts names in English or Polish. Can be specified multiple times."
                ),
            ),
            OpenApiParameter(
                name="player_perspectives",
                description=(
                    "Filter by player perspective name. Accepts names in English or Polish. "
                    "Can be specified multiple times."
                ),
            ),
            OpenApiParameter(
                name="external_games",
                description=(
                    "Filter by external game source. Accepts external game source IDs. "
                    "Can be specified multiple times (e.g. to filter games available on Steam or GOG)."
                ),
            ),
            OpenApiParameter(
                name="ordering",
                description=(
                    "Order results by field. "
                    "Accepted values: rank_position, -rank_position, popularity, -popularity, "
                    "release_date, -release_date, created_at, -created_at. "
                    "Prefix with '-' for descending."
                ),
            ),
        ],
    ),
    retrieve=extend_schema(
        description=(
            "Retrieve a single game by ID. "
            "The detail response includes full relations: genres, platforms, publisher, developer, "
            "game engines, game modes, player perspectives, DLCs, expansions, bundles, "
            "and other related game entries."
        ),
    ),
)
class GameViewSet(ReadOnlyModelViewSet[Game]):
    """A ViewSet for the Game model."""

    queryset = Game.objects.all()
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = GameFilterSet

    def get_queryset(self: Self) -> QuerySet[Game]:
        """Get the queryset for the Game model."""
        queryset = super().get_queryset()
        if self.action == "list":
            return queryset.select_related("stats", "game_status", "game_type")

        return queryset.select_related(
            "stats",
            "publisher",
            "developer",
            "game_status",
            "game_type",
            "parent_game",
        ).prefetch_related(
            "genres",
            "platforms",
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
        )

    def get_serializer_class(
        self: Self,
    ) -> type[GameSerializer | GameSimpleListSerializer]:
        """Get the serializer class for the Game model."""
        if self.action in ("list", "release_calendar"):
            return GameSimpleListSerializer
        return GameSerializer

    @extend_schema(
        description=(
            "Return all games releasing within a specified date range, grouped by day. "
            "Both `start_date` and `end_date` are required; the range must span at most 31 days. "
            "Up to 3 games per day are included in the response, ordered by release date and "
            "then by descending popularity. Returns an empty list if no games fall in the range."
        ),
        request=None,
        parameters=[ReleaseCalendarQuerySerializer],
        responses={200: GameSimpleListSerializer(many=True), 400: None},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="release-calendar",
        pagination_class=None,
        filter_backends=[],
    )
    def release_calendar(self: Self, request: Request) -> Response:
        """Get the game release calendar data."""
        query_serializer = ReleaseCalendarQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        start_date = query_serializer.validated_data.get("start_date")
        end_date = query_serializer.validated_data.get("end_date")

        delta = end_date - start_date
        if delta.days < 0 or delta.days > HIGHEST_NUMBER_OF_DAYS_IN_MONTH:
            return Response(
                {"detail": f"The date range must be between 0 and {HIGHEST_NUMBER_OF_DAYS_IN_MONTH} days."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = (
            self.get_queryset()
            .filter(release_date__range=(start_date, end_date))
            .order_by("release_date", "-stats__popularity")
        )

        grouped_games: dict[dt.date, list[Game]] = {}
        for game in queryset:
            release_date = game.release_date
            if release_date is None:
                continue

            if release_date not in grouped_games:
                grouped_games[release_date] = []

            if len(grouped_games[release_date]) < MAX_GAMES_PER_DAY_IN_CALENDAR:
                grouped_games[release_date].append(game)

        final_games = []
        for date_games in grouped_games.values():
            final_games.extend(date_games)

        serializer = self.get_serializer(final_games, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all game genres. "
            "This is a read-only Lookup Model sourced from IGDB. "
            "Filter by name (bilingual EN/PL partial match) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact genre ID.",
            ),
            OpenApiParameter(
                name="name",
                description=(
                    "Filter by genre name. Searches both the English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the genre's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single genre by ID.",
    ),
)
class GenreViewSet(ReadOnlyModelViewSet[Genre]):
    """A ViewSet for the Genre model."""

    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = GenreFilterSet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all gaming platforms. "
            "This is a read-only Lookup Model sourced from IGDB. "
            "Filter by name (bilingual EN/PL partial match) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact platform ID.",
            ),
            OpenApiParameter(
                name="name",
                description=(
                    "Filter by platform name. Searches both the English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the platform's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single platform by ID.",
    ),
)
class PlatformViewSet(ReadOnlyModelViewSet[Platform]):
    """A ViewSet for the Platform model."""

    queryset = Platform.objects.all()
    serializer_class = PlatformSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = PlatformFilterSet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all game types (e.g. main game, DLC, expansion). "
            "This is a read-only Lookup Model sourced from IGDB. "
            "Filter by type label (bilingual EN/PL) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game type ID.",
            ),
            OpenApiParameter(
                name="type",
                description=(
                    "Filter by game type label. Searches both the English and Polish type fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the game type's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single game type by ID.",
    ),
)
class GameTypeViewSet(ReadOnlyModelViewSet[GameType]):
    """A ViewSet for the GameType model."""

    queryset = GameType.objects.all()
    serializer_class = GameTypeSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = GameTypeFilterSet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all game development statuses (e.g. Released, In Development, Cancelled). "
            "This is a read-only Lookup Model sourced from IGDB. "
            "Filter by status label (bilingual EN/PL) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game status ID.",
            ),
            OpenApiParameter(
                name="status",
                description=(
                    "Filter by status label. Searches both the English and Polish status fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the game status's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single game status by ID.",
    ),
)
class GameStatusViewSet(ReadOnlyModelViewSet[GameStatus]):
    """A ViewSet for the GameStatus model."""

    queryset = GameStatus.objects.all()
    serializer_class = GameStatusSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = GameStatusFilterSet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all game engines (e.g. Unreal Engine, Unity). "
            "This is a read-only Lookup Model sourced from IGDB. "
            "Filter by name (bilingual EN/PL partial match) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game engine ID.",
            ),
            OpenApiParameter(
                name="name",
                description=(
                    "Filter by engine name. Searches both the English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the game engine's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single game engine by ID.",
    ),
)
class GameEngineViewSet(ReadOnlyModelViewSet[GameEngine]):
    """A ViewSet for the GameEngine model."""

    queryset = GameEngine.objects.all()
    serializer_class = GameEngineSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = GameEngineFilterSet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all game modes (e.g. Single player, Multiplayer, Co-operative). "
            "This is a read-only Lookup Model sourced from IGDB. "
            "Filter by name (bilingual EN/PL partial match) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game mode ID.",
            ),
            OpenApiParameter(
                name="name",
                description=(
                    "Filter by game mode name. Searches both the English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the game mode's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single game mode by ID.",
    ),
)
class GameModeViewSet(ReadOnlyModelViewSet[GameMode]):
    """A ViewSet for the GameMode model."""

    queryset = GameMode.objects.all()
    serializer_class = GameModeSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = GameModeFilterSet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all player perspectives (e.g. First person, Third person, Side view). "
            "This is a read-only Lookup Model sourced from IGDB. "
            "Filter by name (bilingual EN/PL partial match) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact player perspective ID.",
            ),
            OpenApiParameter(
                name="name",
                description=(
                    "Filter by perspective name. Searches both the English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the player perspective's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single player perspective by ID.",
    ),
)
class PlayerPerspectiveViewSet(ReadOnlyModelViewSet[PlayerPerspective]):
    """A ViewSet for the PlayerPerspective model."""

    queryset = PlayerPerspective.objects.all()
    serializer_class = PlayerPerspectiveSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = PlayerPerspectiveFilterSet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all external game sources (e.g. Steam, GOG, Epic Games Store). "
            "This is a read-only Lookup Model used to link games to their entries on "
            "external platforms. Filter by name (bilingual EN/PL partial match) or IGDB ID."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact external game source ID.",
            ),
            OpenApiParameter(
                name="name",
                description=(
                    "Filter by source name. Searches both the English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
            OpenApiParameter(
                name="igdb_id",
                description="Filter by the external source's IGDB identifier.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single external game source by ID.",
    ),
)
class ExternalGameSourceViewSet(ReadOnlyModelViewSet[ExternalGameSource]):
    """A ViewSet for the ExternalGameSource model."""

    queryset = ExternalGameSource.objects.all()
    serializer_class = ExternalGameSourceSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = ExternalGameSourceFilterSet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List all game media asset types. "
            "This is a Lookup Model that categorises game media by type (e.g. banner, cover). "
            "Filter by name (bilingual EN/PL partial match)."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact game media ID.",
            ),
            OpenApiParameter(
                name="name",
                description=(
                    "Filter by media type name. Searches both the English and Polish name fields "
                    "(case-insensitive partial match)."
                ),
            ),
        ],
    ),
    create=extend_schema(
        description="Create a new game media record. Requires administrator privileges.",
    ),
    retrieve=extend_schema(
        description="Retrieve a single game media record by ID.",
    ),
    update=extend_schema(
        description="Replace all fields of a game media record. Requires administrator privileges.",
    ),
    partial_update=extend_schema(
        description="Update one or more fields of a game media record. Requires administrator privileges.",
    ),
    destroy=extend_schema(
        description="Delete a game media record. Requires administrator privileges.",
    ),
)
class GameMediaViewSet(ModelViewSet[GameMedia]):
    """A ViewSet for the GameMedia model."""

    queryset = GameMedia.objects.all()
    serializer_class = GameMediaSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filterset_class = GameMediaFilterSet
