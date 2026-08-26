"""Views for the notifications app."""

from typing import TYPE_CHECKING, Self

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import IntegerField
from rest_framework.viewsets import GenericViewSet

from game_list.notifications.filters import NotificationFilterSet
from game_list.notifications.models import Notification
from game_list.notifications.serializers import NotificationSerializer

if TYPE_CHECKING:
    from rest_framework.request import Request

    from game_list.notifications.models import NotificationQuerySet


@extend_schema_view(
    list=extend_schema(
        description=(
            "List notifications for the authenticated user, ordered newest first. "
            "Notifications are generated automatically by system events such as incoming "
            "friendship requests and accepted requests. "
            "Each notification has a category (e.g. FRIENDSHIP), a severity level "
            "(INFO, WARNING, ERROR), and an unread flag."
        ),
        parameters=[
            OpenApiParameter(
                name="category",
                description="Filter by notification category (e.g. FRIENDSHIP).",
            ),
            OpenApiParameter(
                name="level",
                description="Filter by notification severity level (INFO, WARNING, ERROR).",
            ),
            OpenApiParameter(
                name="unread",
                description=(
                    "When true, return only unread notifications. When false, return only read notifications."
                ),
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single notification by ID.",
    ),
    destroy=extend_schema(
        description="Delete a notification permanently.",
    ),
)
class NotificationViewSet(ListModelMixin, RetrieveModelMixin, DestroyModelMixin, GenericViewSet[Notification]):
    """ViewSet for handling notifications."""

    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)
    filterset_class = NotificationFilterSet

    def get_queryset(self: Self) -> NotificationQuerySet:
        """Get the queryset for the current user."""
        user = self.request.user
        if not user.is_authenticated:
            return Notification.objects.none()
        return Notification.objects.filter(recipient=user)

    @extend_schema(
        description="Return the count of unread notifications for the authenticated user.",
        responses={
            200: inline_serializer(
                name="UnreadCountResponse",
                fields={"unread_count": IntegerField(help_text="The count of unread notifications.")},
            ),
        },
    )
    @action(detail=False, methods=("get",), url_path="unread-count")
    def unread_count(self: Self, request: Request) -> Response:  # noqa: ARG002
        """Get the count of unread notifications."""
        count = self.get_queryset().unread().count()
        return Response({"unread_count": count})

    @extend_schema(
        description=(
            "Mark a specific notification as read. "
            "This operation is idempotent: marking an already-read notification has no effect."
        ),
        request=None,
        responses={204: None},
    )
    @action(detail=True, methods=("post",), url_path="mark-as-read")
    def mark_as_read(self: Self, request: Request, pk: int) -> Response:  # noqa: ARG002
        """Mark a specific notification as read."""
        instance = self.get_object()
        instance.mark_as_read()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description=("Mark all unread notifications for the authenticated user as read. This operation is idempotent."),
        request=None,
        responses={204: None},
    )
    @action(detail=False, methods=("post",), url_path="mark-all-as-read")
    def mark_all_as_read(self: Self, request: Request) -> Response:  # noqa: ARG002
        """Mark all notifications as read for the user."""
        self.get_queryset().unread().mark_all_as_read()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description=(
            "Delete all read notifications for the authenticated user permanently. "
            "Unread notifications are not affected."
        ),
        responses={204: None},
    )
    @action(detail=False, methods=("delete",), url_path="delete-all-read")
    def delete_all_read(self: Self, request: Request) -> Response:  # noqa: ARG002
        """Delete all read notifications for the user."""
        self.get_queryset().filter(unread=False).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
