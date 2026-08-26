"""This module contains the custom permission classes."""

from typing import TYPE_CHECKING, ClassVar, Self

from rest_framework import permissions

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class IsAdminOrReadOnly(permissions.IsAdminUser):
    """The request is authenticated as a admin user, or is a read-only request."""

    def has_permission(self: Self, request: Request, view: APIView) -> bool:
        """Check if the request has permission."""
        return bool(request.method in permissions.SAFE_METHODS or super().has_permission(request, view))


class IsOwner(permissions.BasePermission):
    """The request is a safe method, or the requesting user owns the object.

    Ownership is unconditional and has no admin bypass - see ADR-0016. The owning field
    defaults to `user`; subclass and override `owner_field` for models that use a
    different field name (e.g. `sender`/`receiver` on FriendshipRequest).
    """

    owner_field: ClassVar[str] = "user"

    def has_object_permission(self: Self, request: Request, view: APIView, obj: object) -> bool:  # noqa: ARG002
        """Check if the requesting user owns the object, for unsafe methods."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user.is_authenticated and getattr(obj, self.owner_field) == request.user)
