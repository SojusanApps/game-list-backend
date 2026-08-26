"""This module contains the custom permission classes for collections."""

from typing import TYPE_CHECKING, Self

from rest_framework import permissions

from game_list.collections.models import Collection, CollectionItem, CollectionMode, CollectionVisibility
from game_list.friendships.models import Friendship

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class IsCollectionOwner(permissions.BasePermission):
    """Permission to check if user is the collection owner."""

    def has_object_permission(self: Self, request: Request, view: APIView, obj: Collection) -> bool:  # noqa: ARG002
        """Check if user is the owner of the collection."""
        return obj.user == request.user


class IsCollectionOwnerOrCollaborator(permissions.BasePermission):
    """Permission to check if user is owner or collaborator of a collection."""

    def has_object_permission(self: Self, request: Request, view: APIView, obj: Collection) -> bool:  # noqa: ARG002
        """Check if user is owner or collaborator."""
        if not request.user.is_authenticated or request.user.id is None:
            return False

        if obj.user == request.user:
            return True
        if obj.mode == CollectionMode.COLLABORATIVE:
            return obj.collaborators.filter(id=request.user.id).exists()
        return False


class CanViewCollection(permissions.BasePermission):
    """Permission to check if user can view a collection based on visibility."""

    def has_object_permission(self: Self, request: Request, view: APIView, obj: Collection) -> bool:  # noqa: ARG002
        """Check if user can view the collection based on visibility settings."""
        if not request.user.is_authenticated or request.user.id is None:
            return False

        # Owner can always view
        if obj.user == request.user:
            return True

        # Collaborators can always view
        if obj.collaborators.filter(id=request.user.id).exists():
            return True

        # Check visibility
        if obj.visibility == CollectionVisibility.PUBLIC:
            return True

        if obj.visibility == CollectionVisibility.FRIENDS:
            # Check if user is a friend of the owner
            return Friendship.objects.filter(user=obj.user, friend=request.user).exists()

        # PRIVATE - only owner and collaborators (already checked above)
        return False


class CollectionPermission(permissions.BasePermission):
    """Combined permission class for collection operations.

    - List/Retrieve: Anyone, including anonymous visitors - visibility is enforced below
      (and mirrored in CollectionViewSet.get_queryset for list)
    - Create: Any authenticated user
    - Update/Delete: Only owner
    """

    def has_permission(self: Self, request: Request, view: APIView) -> bool:  # noqa: ARG002
        """Safe methods are open to anyone; unsafe methods require authentication."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self: Self, request: Request, view: APIView, obj: Collection) -> bool:  # noqa: ARG002
        """Check object-level permissions."""
        # Owner can do anything
        if request.user.is_authenticated and obj.user == request.user:
            return True

        # For unsafe methods (PUT, PATCH, DELETE), only owner allowed
        if request.method not in permissions.SAFE_METHODS:
            return False

        return self._is_visible(request, obj)

    @staticmethod
    def _is_visible(request: Request, obj: Collection) -> bool:
        """Check whether a non-owner viewer can see a collection based on visibility."""
        if obj.visibility == CollectionVisibility.PUBLIC:
            return True

        if not request.user.is_authenticated:
            return False

        # Collaborators can always view
        if obj.collaborators.filter(id=request.user.id).exists():
            return True

        if obj.visibility == CollectionVisibility.FRIENDS:
            return Friendship.objects.filter(user=obj.user, friend=request.user).exists()

        return False


class CollectionItemPermission(permissions.BasePermission):
    """Permission class for collection item operations.

    - List/Retrieve: Anyone, including anonymous visitors - filtered by collection
      visibility (mirrored in CollectionItemViewSet.get_queryset for list)
    - Create: Owner or collaborator (if COLLABORATIVE mode)
    - Update/Delete: Owner or collaborator (if COLLABORATIVE mode)
    """

    def has_permission(self: Self, request: Request, view: APIView) -> bool:  # noqa: ARG002
        """Safe methods are open to anyone; unsafe methods require authentication."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self: Self, request: Request, view: APIView, obj: CollectionItem) -> bool:  # noqa: ARG002
        """Check object-level permissions for collection item."""
        collection = obj.collection

        # Collection owner can do anything
        if request.user.is_authenticated and collection.user == request.user:
            return True

        if request.method in permissions.SAFE_METHODS:
            return self._is_visible(request, collection)

        # For unsafe methods, must be authenticated owner or collaborator in COLLABORATIVE mode
        if not request.user.is_authenticated:
            return False
        is_collaborator = collection.collaborators.filter(id=request.user.id).exists()
        return collection.mode == CollectionMode.COLLABORATIVE and is_collaborator

    @staticmethod
    def _is_visible(request: Request, collection: Collection) -> bool:
        """Check whether a non-owner viewer can see a collection based on visibility."""
        if collection.visibility == CollectionVisibility.PUBLIC:
            return True

        if not request.user.is_authenticated:
            return False

        if collection.collaborators.filter(id=request.user.id).exists():
            return True

        if collection.visibility == CollectionVisibility.FRIENDS:
            return Friendship.objects.filter(user=collection.user, friend=request.user).exists()

        return False
