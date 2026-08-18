"""This module contains the viewsets for user related interactions."""

from typing import TYPE_CHECKING, Self

from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request

from my_game_list.users.filters import UserFilterSet
from my_game_list.users.models import User as UserModel
from my_game_list.users.serializers import UserDetailSerializer, UserSerializer

User: type[UserModel] = get_user_model()


@extend_schema_view(
    list=extend_schema(
        description=(
            "List user accounts. A non-staff user only sees active accounts; "
            "is_staff users see every account, active or inactive. "
            "Filter by username (partial match), gender, or active status."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                description="Filter by exact user ID.",
            ),
            OpenApiParameter(
                name="username",
                description="Filter by username. Case-insensitive partial match.",
            ),
            OpenApiParameter(
                name="gender",
                description=("Filter by gender. Can be specified multiple times to match several values."),
            ),
            OpenApiParameter(
                name="is_active",
                description="Filter by account active status. When true, return only active accounts.",
            ),
        ],
    ),
    retrieve=extend_schema(
        description=(
            "Retrieve a user account by ID. Non-staff users get a 404 for an inactive account. "
            "The authenticated account owner receives additional private fields "
            "(e.g. email address) that are not visible to other users."
        ),
    ),
)
class UserViewSet(GenericViewSet[UserModel], ListModelMixin, RetrieveModelMixin):
    """ViewSet is responsible for listing and retrieving user information."""

    queryset = User.objects.all()
    filterset_class = UserFilterSet
    permission_classes = (IsAuthenticated,)

    def get_queryset(self: Self) -> QuerySet[UserModel]:
        """Scope visible users: staff see everyone, everyone else sees only active accounts."""
        user = self.request.user
        queryset: QuerySet[UserModel] = super().get_queryset()

        if not user.is_authenticated:
            return queryset.none()

        if user.is_staff:
            return queryset

        return queryset.filter(is_active=True)

    def get_serializer_class(self: Self) -> type[UserSerializer | UserDetailSerializer]:
        """Get the serializer class for the User model."""
        if self.action == "retrieve":
            return UserDetailSerializer
        return UserSerializer

    @extend_schema(
        description="Retrieve the authenticated caller's own account, resolved from their Keycloak identity.",
        responses={200: UserDetailSerializer},
    )
    @action(detail=False, methods=["get"], url_path="me")
    def me(self: Self, request: Request) -> Response:
        """Return the requesting user's own account."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        return Response(UserDetailSerializer(request.user, context=self.get_serializer_context()).data)
