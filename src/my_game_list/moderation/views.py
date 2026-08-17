"""This module contains the viewsets for moderation related interactions."""

from typing import TYPE_CHECKING, Self

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from my_game_list.moderation.filters import ReportFilterSet
from my_game_list.moderation.models import Report
from my_game_list.moderation.serializers import ReportCreateSerializer, ReportSerializer

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request


@extend_schema_view(
    list=extend_schema(
        description=(
            "List reports. A non-staff user only sees reports they personally filed; "
            "is_staff users see every report, regardless of who filed it."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact report ID.",
            ),
            OpenApiParameter(
                name="target_type",
                description=(
                    "Filter by what the report targets. Accepted values: avatar, username, review, "
                    "translation_suggestion, game_list_note, collection, collection_item_note."
                ),
            ),
            OpenApiParameter(
                name="status",
                description="Filter by lifecycle status. Accepted values: pending, accepted, rejected.",
            ),
            OpenApiParameter(
                name="reported_by",
                description="Filter by the ID of the user who filed the report.",
            ),
            OpenApiParameter(
                name="reported_user",
                description="Filter by the ID of the user whose content or profile field was reported.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a single report by ID.",
    ),
)
class ReportViewSet(GenericViewSet[Report], ListModelMixin, RetrieveModelMixin, CreateModelMixin):
    """A ViewSet for submitting and reviewing reports."""

    queryset = Report.objects.all()
    permission_classes = (IsAuthenticated,)
    filterset_class = ReportFilterSet

    def get_serializer_class(self: Self) -> type[ReportCreateSerializer | ReportSerializer]:
        """Get the serializer class for the report viewset."""
        return ReportCreateSerializer if self.action == "create" else ReportSerializer

    def get_queryset(self: Self) -> QuerySet[Report]:
        """Scope visible reports: staff see everything, everyone else sees only what they filed."""
        user = self.request.user
        queryset: QuerySet[Report] = super().get_queryset()

        if not user.is_authenticated:
            return queryset.none()

        if user.is_staff:
            return queryset

        return queryset.filter(reported_by=user)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def accept(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Accept a pending report: flag the target as moderated and issue a warning."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        report = self.get_object()
        report.accept(request.user)
        serializer = self.get_serializer(report)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def reject(self: Self, request: Request, pk: str | None = None) -> Response:  # noqa: ARG002
        """Reject a pending report. No flag changes, no warning, no notification."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        report = self.get_object()
        rejection_reason = request.data.get("rejection_reason", "") if isinstance(request.data, dict) else ""
        report.reject(request.user, rejection_reason=rejection_reason)
        serializer = self.get_serializer(report)
        return Response(serializer.data)
