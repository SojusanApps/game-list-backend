"""This module contains the viewsets for user related interactions."""

from typing import TYPE_CHECKING, Self

from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

if TYPE_CHECKING:
    from rest_framework.authentication import BaseAuthentication
    from rest_framework.request import Request

from my_game_list.users.filters import UserFilterSet
from my_game_list.users.models import User as UserModel
from my_game_list.users.serializers import (
    ChangePasswordSerializer,
    ChangeUsernameSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserSerializer,
)

User: type[UserModel] = get_user_model()


@extend_schema_view(
    list=extend_schema(
        description=(
            "List user accounts. Returns public user information for all users. "
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
            "Retrieve a user account by ID. "
            "The authenticated account owner receives additional private fields "
            "(e.g. email address) that are not visible to other users."
        ),
    ),
    create=extend_schema(
        description=(
            "Register a new user account. "
            "This endpoint is publicly accessible and requires no authentication. "
            "Provide a unique username, a valid email address, and a password meeting "
            "the site's complexity requirements."
        ),
    ),
)
class UserViewSet(GenericViewSet[UserModel], ListModelMixin, RetrieveModelMixin, CreateModelMixin):
    """ViewSet is responsible for creating, listing, and retrieving user information."""

    queryset = User.objects.all()
    filterset_class = UserFilterSet

    def get_serializer_class(
        self: Self,
    ) -> type[UserCreateSerializer | UserSerializer | UserDetailSerializer]:
        """Get the serializer class for the User model."""
        if self.action == "retrieve":
            return UserDetailSerializer
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_authenticators(self: Self) -> list[BaseAuthentication]:
        """Get the authenticators for the actions.

        During real request dispatch, `self.action` isn't set yet at this point (it's
        assigned later in `initialize_request`), but `self.request` already is (set by the
        router's `as_view()` closure before `dispatch()` runs) - so `self.action_map` is used
        to resolve the current action from the request method. Schema generation is the
        opposite: `self.action` is already set, but `self.request` is explicitly `None`, so
        `self.action` is used directly whenever it's available to avoid touching `self.request`.
        """
        action = getattr(self, "action", None)
        if action is None and self.request is not None:
            action = self.action_map.get((self.request.method or "").lower())

        if action == "create":
            return []

        return super().get_authenticators()

    def get_permissions(self: Self) -> list[BasePermission]:
        """Get the permissions for the actions."""
        permission_classes = (AllowAny,) if self.action == "create" else (IsAuthenticated,)
        return [permission() for permission in permission_classes]

    @extend_schema(
        description=(
            "Change the authenticated user's own username. "
            "The new username must be unique, differ from the current one, and follow the same "
            "format rules as registration. Regenerates the user's slug (and every slug of their "
            "owned collections) from the new username, resolving any collision with a numeric suffix."
        ),
        request=ChangeUsernameSerializer,
        responses={200: UserDetailSerializer},
    )
    @action(detail=False, methods=["post"], url_path="change-username")
    def change_username(self: Self, request: Request) -> Response:
        """Change the requesting user's own username, regenerating their slug."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        user = request.user
        serializer = ChangeUsernameSerializer(instance=user, data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user.username = serializer.validated_data["username"]
            user.slug = ""
            user.save()

            for collection in user.collections.all():
                collection.slug = ""
                collection.save()

        return Response(UserDetailSerializer(user, context=self.get_serializer_context()).data)

    @extend_schema(
        description=(
            "Change the authenticated user's own password. "
            "Requires the current password for re-verification. "
            "The new password is validated with the same strength rules used at registration. "
            "Does not invalidate already-issued tokens on other devices."
        ),
        request=ChangePasswordSerializer,
        responses={204: None},
    )
    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self: Self, request: Request) -> Response:
        """Change the requesting user's own password."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        user = request.user
        serializer = ChangePasswordSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
