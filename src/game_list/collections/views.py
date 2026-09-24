"""This module contains the viewsets for the collection related data."""

from decimal import Decimal
from typing import TYPE_CHECKING, Self, cast

from django.db.models import BooleanField, Exists, F, Max, OuterRef, Q, Value
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import CharField, DecimalField
from rest_framework.viewsets import ModelViewSet

from game_list.collections.filters import CollectionFilterSet, CollectionItemFilterSet
from game_list.collections.models import (
    Collection,
    CollectionFavorite,
    CollectionItem,
    CollectionMode,
    CollectionVisibility,
)
from game_list.collections.permissions import (
    CollectionItemPermission,
    CollectionPermission,
    IsCollectionOwnerOrCollaborator,
)
from game_list.collections.serializers import (
    CollectionCreateSerializer,
    CollectionDetailSerializer,
    CollectionItemBulkReorderSerializer,
    CollectionItemCreateSerializer,
    CollectionItemReorderSerializer,
    CollectionItemSerializer,
    CollectionItemTierUpdateSerializer,
    CollectionSerializer,
)
from game_list.friendships.models import Friendship

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request

    from game_list.users.models import User


@extend_schema_view(
    list=extend_schema(
        description=(
            "List collections visible to the authenticated user. "
            "The response includes: the user's own collections, collections they collaborate on, "
            "all PUBLIC collections, and FRIENDS collections owned by their friends. "
            "PRIVATE collections are only visible to their owner. "
            "`is_favorite` reflects the requesting user's own favorite."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact collection ID.",
            ),
            OpenApiParameter(
                name="name",
                description="Filter by collection name. Case-insensitive partial match.",
            ),
            OpenApiParameter(
                name="user",
                description="Filter by owner user ID. Returns only collections owned by that user.",
            ),
            OpenApiParameter(
                name="collaborator",
                description=(
                    "Filter by collaborator user ID. Returns collections where that user is listed "
                    "as a collaborator but is NOT the owner."
                ),
            ),
            OpenApiParameter(
                name="member",
                description=(
                    "Filter by member user ID. Returns collections where the user is either the "
                    "owner OR a collaborator. Unlike `user` (owner only) and `collaborator` "
                    "(collaborator only), `member` matches both roles."
                ),
            ),
            OpenApiParameter(
                name="visibility",
                description=(
                    "Filter by visibility level. "
                    "Accepted values: PUBLIC, FRIENDS, PRIVATE. "
                    "Can be specified multiple times to match several values."
                ),
            ),
            OpenApiParameter(
                name="mode",
                description=(
                    "Filter by collection mode. "
                    "Accepted values: STANDARD, TIER_LIST, COLLABORATIVE. "
                    "Can be specified multiple times."
                ),
            ),
            OpenApiParameter(
                name="type",
                description=(
                    "Filter by collection type (e.g. GAMES). "
                    "Can be specified multiple times to match several values."
                ),
            ),
            OpenApiParameter(
                name="is_favorite",
                description=(
                    "When true, return only collections the requesting user has favorited; when false, only "
                    "those they have not. Favorites are per user, so anonymous visitors have none."
                ),
            ),
        ],
    ),
    create=extend_schema(
        description=(
            "Create a new collection. The authenticated user is automatically set as the owner. "
            "Favorites are not part of the payload; use the `favorite` endpoint."
        ),
    ),
    retrieve=extend_schema(
        description=(
            "Retrieve a single collection by ID. Returns full detail including collaborators "
            "and the list of items. Visibility rules apply: PRIVATE collections are only "
            "accessible to their owner. `is_favorite` reflects the requesting user's own favorite."
        ),
    ),
    update=extend_schema(
        description="Replace all editable fields of an existing collection. Requires ownership.",
    ),
    partial_update=extend_schema(
        description="Update one or more fields of an existing collection. Requires ownership.",
    ),
    destroy=extend_schema(
        description="Delete a collection and all its items permanently. Requires ownership.",
    ),
)
class CollectionViewSet(ModelViewSet[Collection]):
    """A ViewSet for the Collection model.

    Permissions:
    - List/Retrieve: Open to anonymous visitors too; returns visible collections based on
      visibility (own, collaborated, PUBLIC, or FRIENDS collections owned by an authenticated
      friend - an anonymous visitor only ever sees PUBLIC collections)
    - Create: Any authenticated user
    - Update/Delete: Only owner
    - Favorite/Unfavorite: Any authenticated user who can see the collection
    """

    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
    permission_classes = (CollectionPermission,)
    filterset_class = CollectionFilterSet

    def get_queryset(self: Self) -> QuerySet[Collection]:
        """Get the queryset filtered by visibility permissions.

        Returns collections that the user can see:
        - Own collections
        - Collections where user is a collaborator
        - Public collections
        - Friends' collections (visibility = FRIENDS)
        """
        queryset = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            # Anonymous users can only see public collections and have no favorites
            return queryset.filter(visibility=CollectionVisibility.PUBLIC).annotate(
                is_favorite=Value(value=False, output_field=BooleanField()),
            )

        # Favorites are per user: each viewer sees only their own
        queryset = queryset.annotate(
            is_favorite=Exists(CollectionFavorite.objects.filter(collection=OuterRef("pk"), user=user)),
        )

        # Get IDs of friends
        friend_ids = Friendship.objects.filter(user=user).values_list("friend_id", flat=True)

        # Filter: own collections OR collaborator OR public OR friends' with FRIENDS visibility
        queryset = queryset.filter(
            Q(user=user)  # Own collections
            | Q(collaborators=user)  # Collaborator
            | Q(visibility=CollectionVisibility.PUBLIC)  # Public collections
            | Q(user_id__in=friend_ids, visibility=CollectionVisibility.FRIENDS),  # Friends' collections
        ).distinct()

        if self.action == "retrieve":
            return queryset.select_related("user").prefetch_related("collaborators", "items", "items__game")
        return queryset.select_related("user").prefetch_related("collaborators")

    def get_serializer_class(
        self: Self,
    ) -> type[CollectionCreateSerializer | CollectionSerializer | CollectionDetailSerializer]:
        """Get the serializer class for the Collection model."""
        if self.action in ["create", "update", "partial_update"]:
            return CollectionCreateSerializer
        if self.action == "retrieve":
            return CollectionDetailSerializer
        return CollectionSerializer

    def perform_create(self: Self, serializer: CollectionCreateSerializer) -> None:  # type: ignore[override]
        """Set the user to the current user when creating a collection."""
        serializer.save(user=self.request.user)

    def _calculate_fractional_order(
        self: Self,
        collection: Collection,
        position: int,
        tier: str = "",
        exclude_item: CollectionItem | None = None,
    ) -> Decimal:
        """Calculate fractional order for an item at the given position.

        Args:
            collection: The collection containing the items
            position: The target position (0-based index)
            tier: The tier to calculate order within (empty string for non-tier lists)
            exclude_item: Item to exclude from calculation (when reordering an existing item)

        Returns:
            Decimal: The calculated fractional order value
        """
        items = CollectionItem.objects.filter(
            collection=collection,
            tier=tier,
        )

        # Exclude the item being moved to get the correct target position
        if exclude_item:
            items = items.exclude(id=exclude_item.id)

        items = items.order_by("order", "id")

        items_list = list(items)
        total_items = len(items_list)

        # Position at beginning
        if position == 0:
            if total_items == 0:
                return Decimal("1.0")
            first_order = items_list[0].order or Decimal("1.0")
            return first_order / Decimal("2.0")

        # Position at or beyond end
        if position >= total_items:
            if total_items == 0:
                return Decimal("1.0")
            last_order = items_list[-1].order or Decimal("1.0")
            return last_order + Decimal("1.0")

        # Position in the middle - between two items
        prev_item = items_list[position - 1]
        next_item = items_list[position]

        prev_order = prev_item.order or Decimal("1.0")
        next_order = next_item.order or Decimal("2.0")

        # If orders are equal (e.g., due to data inconsistencies), avoid returning
        # a duplicate midpoint by falling back to appending at the end.
        if prev_order == next_order:
            last_order = items_list[-1].order or Decimal("1.0")
            return last_order + Decimal("1.0")

        # Calculate midpoint
        return (prev_order + next_order) / Decimal("2.0")

    @extend_schema(
        description=(
            "Add the collection to the requesting user's favorites. Any authenticated user who can see "
            "the collection may do so; a collection that is not visible to them returns 404. Favorites are "
            "private to the user and independent of the owner's. Idempotent: favoriting an already "
            "favorited collection succeeds without change."
        ),
        request=None,
        responses={204: None},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="favorite",
        permission_classes=[IsAuthenticated],
    )
    def favorite(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Favorite the collection for the requesting user."""
        collection = self.get_object()
        CollectionFavorite.objects.get_or_create(collection=collection, user=cast("User", request.user))

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description=(
            "Remove the collection from the requesting user's favorites. Other users' favorites are "
            "unaffected. Idempotent: unfavoriting a collection that is not favorited succeeds without change."
        ),
        request=None,
        responses={204: None},
    )
    @favorite.mapping.delete
    def unfavorite(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Remove the collection from the requesting user's favorites."""
        collection = self.get_object()
        CollectionFavorite.objects.filter(collection=collection, user=cast("User", request.user)).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description=(
            "Move a single item to a new position within its current tier using fractional "
            "indexing. The server calculates a new fractional order value based on the target "
            "position and its neighbors; no other items are modified. "
            "Position is 0-based: 0 places the item at the top of the tier."
        ),
        request=CollectionItemReorderSerializer,
        parameters=[
            OpenApiParameter(
                name="item_id",
                description="ID of the collection item to reorder",
                required=True,
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
            ),
        ],
        responses={
            200: inline_serializer(
                name="CollectionItemReorderResponse",
                fields={
                    "order": DecimalField(
                        help_text="The new fractional order of the item after reordering.",
                        min_value=Decimal("0.0"),
                        max_digits=20,
                        decimal_places=10,
                    ),
                },
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="items/(?P<item_id>[^/.]+)/reorder",
        permission_classes=[IsAuthenticated, IsCollectionOwnerOrCollaborator],
    )
    def reorder_item(
        self: Self,
        request: Request,
        pk: str | None = None,  # noqa: ARG002
        item_id: str | None = None,
    ) -> Response:
        """Reorder a single item in the collection using fractional indexing.

        The backend calculates the fractional order based on the target position
        and its neighbors. This allows inserting items without renumbering others.

        Args:
            request: The HTTP request containing position data
            pk: Collection ID (from URL)
            item_id: ID of the item to reorder (from URL)

        Expected payload:
        {
            "position": 2  # 0-based index of the new position within the same tier
        }
        """
        collection = self.get_object()
        serializer = CollectionItemReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        position = serializer.validated_data["position"]

        # Get the item to reorder
        try:
            item = CollectionItem.objects.get(id=int(item_id) if item_id else 0, collection=collection)
        except CollectionItem.DoesNotExist:
            return Response(
                {"detail": f"Item with ID {item_id} not found in this collection."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Calculate new fractional order based on position and neighbors
        new_order = self._calculate_fractional_order(collection, position, tier=item.tier, exclude_item=item)

        # Update the item's order
        item.order = new_order
        item.save(update_fields=["order"])

        return Response({"order": str(new_order)}, status=status.HTTP_200_OK)

    @extend_schema(
        description=(
            "Move a single item to a different tier, and optionally reposition it within that tier. "
            "If no `position` is provided, the item is appended at the end of the target tier. "
            "If `position` is provided (0-based index), fractional indexing places the item precisely."
        ),
        request=CollectionItemTierUpdateSerializer,
        parameters=[
            OpenApiParameter(
                name="item_id",
                description="ID of the collection item to reorder",
                required=True,
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
            ),
        ],
        responses={
            200: inline_serializer(
                name="CollectionItemTierUpdateResponse",
                fields={
                    "tier": CharField(
                        help_text="The new tier of the item after the update.",
                    ),
                    "order": DecimalField(
                        help_text="The new fractional order of the item within the new tier.",
                        min_value=Decimal("0.0"),
                        max_digits=20,
                        decimal_places=10,
                    ),
                },
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="items/(?P<item_id>[^/.]+)/update-tier",
        permission_classes=[IsAuthenticated, IsCollectionOwnerOrCollaborator],
    )
    def update_tier(
        self: Self,
        request: Request,
        pk: str | None = None,  # noqa: ARG002
        item_id: str | None = None,
    ) -> Response:
        """Update tier and optionally position for a single item.

        When changing tiers, you can optionally specify a new position within that tier.
        If no position is provided, the item will be placed at the end of the new tier.

        Args:
            request: The HTTP request containing tier and optional position data
            pk: Collection ID (from URL)
            item_id: ID of the item to update (from URL)

        Expected payload:
        {
            "tier": "S",
            "position": 1  # Optional
        }
        """
        collection = self.get_object()
        serializer = CollectionItemTierUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tier = serializer.validated_data["tier"]
        position = serializer.validated_data.get("position")

        # Get the item to update
        try:
            item = CollectionItem.objects.get(id=int(item_id) if item_id else 0, collection=collection)
        except CollectionItem.DoesNotExist:
            return Response(
                {"detail": f"Item with ID {item_id} not found in this collection."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Update tier
        item.tier = tier

        # Calculate new order if position is provided, otherwise append to end
        if position is not None:
            new_order = self._calculate_fractional_order(collection, position, tier=tier, exclude_item=item)
        else:
            # Append to end of new tier
            max_order = CollectionItem.objects.filter(
                collection=collection,
                tier=tier,
            ).aggregate(
                Max("order"),
            )["order__max"]
            new_order = (Decimal(str(max_order)) if max_order else Decimal("0.0")) + Decimal("1.0")

        item.order = new_order
        item.save(update_fields=["tier", "order"])

        return Response({"tier": tier, "order": str(new_order)}, status=status.HTTP_200_OK)

    @extend_schema(
        description=(
            "Reorder all items in a collection in a single request by assigning explicit positions. "
            "The fractional ordering state is reset: every item receives a clean integer order equal "
            "to its declared position. The payload must include every item currently in the "
            "collection; missing or extra items cause an error."
        ),
        request=CollectionItemBulkReorderSerializer,
        responses={204: None},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="bulk-reorder",
        permission_classes=[IsAuthenticated, IsCollectionOwnerOrCollaborator],
    )
    def bulk_reorder(
        self: Self,
        request: Request,
        pk: str | None = None,  # noqa: ARG002
    ) -> Response:
        """Bulk-reorder all items in the collection by assigning explicit positions.

        Accepts a list of all collection item IDs with their new positions. The
        fractional ordering state is reset: each item receives a clean integer
        order value equal to its declared position. Every item currently in the
        collection must be present in the payload.

        Args:
            request: The HTTP request containing the items list.
            pk: Collection ID (from URL).

        Expected payload:
        {
            "items": [
                {"id": 5, "position": 0},
                {"id": 3, "position": 1},
                {"id": 7, "position": 2}
            ]
        }
        """
        collection = self.get_object()
        serializer = CollectionItemBulkReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items_data: list[dict[str, int]] = serializer.validated_data["items"]
        item_ids = [entry["id"] for entry in items_data]

        # Fetch items that belong to this collection
        db_items = CollectionItem.objects.filter(collection=collection, id__in=item_ids)
        db_items_dict = {item.id: item for item in db_items}

        if len(db_items_dict) != len(item_ids):
            missing = set(item_ids) - set(db_items_dict)
            return Response(
                {"detail": f"Items not found in this collection: {sorted(missing)}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate that the payload covers every item in the collection
        total_in_collection = CollectionItem.objects.filter(collection=collection).count()
        if len(item_ids) != total_in_collection:
            return Response(
                {"detail": "The payload must include all items in the collection."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Assign new integer order values, resetting fractional ordering
        for entry in items_data:
            db_items_dict[entry["id"]].order = Decimal(str(entry["position"]))

        CollectionItem.objects.bulk_update(list(db_items_dict.values()), ["order"])

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(
        description=(
            "List collection items visible to the authenticated user, ordered by position (ascending). "
            "Only items from accessible collections are returned: own collections, collaborated "
            "collections, PUBLIC collections, and FRIENDS collections from friends. "
            "Items with no order value appear last."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact collection item ID.",
            ),
            OpenApiParameter(
                name="collection",
                description="Filter by parent collection ID.",
            ),
            OpenApiParameter(
                name="game",
                description="Filter by game ID. Returns only items linked to that game.",
            ),
            OpenApiParameter(
                name="tier",
                description=(
                    "Filter by tier label (e.g. S, A, B). Only relevant for TIER_LIST collections. "
                    "Can be specified multiple times to match several tiers."
                ),
            ),
            OpenApiParameter(
                name="has_tier",
                description=(
                    "When true, return only items that are assigned to a tier. "
                    "When false, return only items that have no tier assigned."
                ),
            ),
            OpenApiParameter(
                name="added_by",
                description="Filter by the user ID who added the item to the collection.",
            ),
            OpenApiParameter(
                name="ordering",
                description=(
                    "Order results by field. "
                    "Accepted values: order, -order, created_at, -created_at, tier, -tier. "
                    "Prefix with '-' for descending order."
                ),
            ),
        ],
    ),
    create=extend_schema(
        description=(
            "Add a game to a collection. The authenticated user is recorded as the item creator. "
            "Write access requires ownership or collaborator status in COLLABORATIVE mode."
        ),
    ),
    retrieve=extend_schema(
        description="Retrieve a single collection item by ID.",
    ),
    update=extend_schema(
        description="Replace all editable fields of a collection item.",
    ),
    partial_update=extend_schema(
        description="Update one or more fields of a collection item.",
    ),
    destroy=extend_schema(
        description="Remove an item from its collection permanently.",
    ),
)
class CollectionItemViewSet(ModelViewSet[CollectionItem]):
    """A ViewSet for the CollectionItem model.

    Permissions:
    - List/Retrieve: Open to anonymous visitors too; filtered by collection visibility
      (an anonymous visitor only ever sees items from PUBLIC collections)
    - Create/Update/Delete: Owner or collaborator (if COLLABORATIVE mode)
    """

    queryset = CollectionItem.objects.all()
    serializer_class = CollectionItemSerializer
    permission_classes = (CollectionItemPermission,)
    filterset_class = CollectionItemFilterSet

    def get_queryset(self: Self) -> QuerySet[CollectionItem]:
        """Get the queryset filtered by collection visibility.

        Users can only see items from collections they can access.
        Items are ordered by the 'order' field (ascending, lowest first).
        """
        queryset = super().get_queryset().select_related("collection", "game", "added_by")
        user = self.request.user

        if not user.is_authenticated:
            return queryset.filter(collection__visibility=CollectionVisibility.PUBLIC).order_by(
                F("order").asc(nulls_last=True),
            )

        # Get IDs of friends
        friend_ids = Friendship.objects.filter(user=user).values_list("friend_id", flat=True)

        # Filter items based on collection visibility
        return (
            queryset.filter(
                Q(collection__user=user)  # Own collections
                | Q(collection__collaborators=user)  # Collaborator
                | Q(collection__visibility=CollectionVisibility.PUBLIC)  # Public
                | Q(collection__user_id__in=friend_ids, collection__visibility=CollectionVisibility.FRIENDS),
            )
            .distinct()
            .order_by(F("order").asc(nulls_last=True))
        )

    def get_serializer_class(
        self: Self,
    ) -> type[CollectionItemCreateSerializer | CollectionItemSerializer]:
        """Get the serializer class for the CollectionItem model."""
        if self.action in ["create", "update", "partial_update"]:
            return CollectionItemCreateSerializer
        return CollectionItemSerializer

    def perform_create(self: Self, serializer: CollectionItemCreateSerializer) -> None:  # type: ignore[override]
        """Set the added_by to the current user and validate collection permissions."""
        collection = serializer.validated_data.get("collection")

        # Check if user can add items to this collection
        if collection.user != self.request.user:
            if collection.mode != CollectionMode.COLLABORATIVE:
                message = _("Only the owner can add items to non-collaborative collections.")
                raise PermissionDenied(message)
            if not collection.collaborators.filter(id=self.request.user.id).exists():
                message = _("You must be a collaborator to add items to this collection.")
                raise PermissionDenied(message)

        # Calculate order using fractional indexing for items with empty tier
        max_order = CollectionItem.objects.filter(
            collection=collection,
            tier=serializer.validated_data.get("tier", ""),
        ).aggregate(Max("order"))["order__max"]

        next_order = Decimal("1.0") if max_order is None else Decimal(str(max_order)) + Decimal("1.0")

        serializer.save(added_by=self.request.user, order=next_order)
