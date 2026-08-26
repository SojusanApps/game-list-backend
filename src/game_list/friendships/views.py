"""This module contains the viewsets for the friendship related data."""

from typing import TYPE_CHECKING, Self

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from game_list.friendships.filters import (
    FriendshipFilterSet,
    FriendshipRequestFilterSet,
)
from game_list.friendships.models import Friendship, FriendshipRequest
from game_list.friendships.permissions import IsFriendshipRequestReceiver, IsFriendshipRequestSender
from game_list.friendships.serializers import (
    FriendshipRequestCreateSerializer,
    FriendshipRequestSerializer,
    FriendshipSerializer,
)
from game_list.notifications.constants import NotificationCategory, NotificationVerb
from game_list.notifications.utils import notify_send

if TYPE_CHECKING:
    from rest_framework.request import Request


User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        description=(
            "List confirmed friendships for the authenticated user. "
            "A Friendship is a bidirectional, established relationship. "
            "Each record represents one direction of the relationship."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact friendship record ID.",
            ),
            OpenApiParameter(
                name="user",
                description="Filter by user ID.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single friendship record by ID.",
    ),
    destroy=extend_schema(
        description=(
            "End a friendship. Either party may delete it; deleting either party's record "
            "removes both reciprocal records, ending the friendship for both users."
        ),
    ),
)
class FriendshipViewSet(ListModelMixin, RetrieveModelMixin, DestroyModelMixin, GenericViewSet["Friendship"]):
    """All views related to friendship."""

    queryset = Friendship.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = FriendshipSerializer
    filterset_class = FriendshipFilterSet

    def get_queryset(self: Self) -> QuerySet[Friendship]:
        """Restrict list/retrieve/destroy to friendships the requesting user is a party to."""
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        return queryset.filter(Q(user=user) | Q(friend=user))


@extend_schema_view(
    list=extend_schema(
        description=(
            "List friendship requests. "
            "Returns requests sent by or directed to authenticated users. "
            "Use the `sender` and `receiver` filters to narrow results."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact friendship request ID.",
            ),
            OpenApiParameter(
                name="sender",
                description="Filter by the user ID who sent the request.",
            ),
            OpenApiParameter(
                name="receiver",
                description="Filter by the user ID who received the request.",
            ),
        ],
    ),
    create=extend_schema(
        description="Send a friendship request to another user. A notification is sent to the recipient.",
    ),
    retrieve=extend_schema(
        description="Retrieve a single friendship request by ID.",
    ),
    destroy=extend_schema(
        description="Cancel a friendship request before it is accepted or rejected.",
    ),
)
class FriendshipRequestViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    DestroyModelMixin,
    GenericViewSet["FriendshipRequest"],
):
    """All views related to friendship requests."""

    queryset = FriendshipRequest.objects.all()
    permission_classes = (IsAuthenticated,)
    filterset_class = FriendshipRequestFilterSet

    def get_queryset(self: Self) -> QuerySet[FriendshipRequest]:
        """Restrict list/retrieve to friendship requests the requesting user sent or received."""
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        return queryset.filter(Q(sender=user) | Q(receiver=user))

    def get_permissions(self: Self) -> list[BasePermission]:
        """Only the sender may withdraw (destroy) their own pending request."""
        if self.action == "destroy":
            return [IsAuthenticated(), IsFriendshipRequestSender()]
        return super().get_permissions()  # type: ignore[return-value]

    def get_serializer_class(
        self: Self,
    ) -> type[FriendshipRequestCreateSerializer | FriendshipRequestSerializer]:
        """Get the serializer class for the request."""
        return FriendshipRequestCreateSerializer if self.action == "create" else FriendshipRequestSerializer

    def perform_create(self: Self, serializer: serializers.BaseSerializer[FriendshipRequest]) -> None:
        """Create a friendship request and send a notification."""
        user = self.request.user
        if not user.is_authenticated:
            return
        instance = serializer.save(sender=user)
        notify_send(
            sender=user,
            recipient=instance.receiver,
            verb=NotificationVerb.FRIEND_REQUEST_SENT,
            category=NotificationCategory.FRIENDSHIP,
        )

    @extend_schema(
        description=(
            "Accept a pending friendship request. "
            "Creates reciprocal Friendship records for both the sender and receiver, "
            "and sends a notification to the original sender confirming the acceptance."
        ),
        request=None,
        responses={204: None},
    )
    @action(detail=True, methods=("post",), permission_classes=[IsAuthenticated, IsFriendshipRequestReceiver])
    def accept(self: Self, request: Request, pk: int) -> Response:  # noqa: ARG002
        """Accept a friendship request."""
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        instance: FriendshipRequest = self.get_object()
        instance.accept()

        notify_send(
            sender=user,
            recipient=instance.sender,
            verb=NotificationVerb.FRIEND_REQUEST_ACCEPTED,
            category=NotificationCategory.FRIENDSHIP,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description=(
            "Reject a pending friendship request. "
            "The request record is kept with `rejected_at` set. No notification is sent to the requester."
        ),
        request=None,
        responses={204: None},
    )
    @action(detail=True, methods=("post",), permission_classes=[IsAuthenticated, IsFriendshipRequestReceiver])
    def reject(self: Self, request: Request, pk: int) -> Response:  # noqa: ARG002
        """Reject a friendship request."""
        instance: FriendshipRequest = self.get_object()
        instance.reject()

        return Response(status=status.HTTP_204_NO_CONTENT)
