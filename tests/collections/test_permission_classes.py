"""Direct unit tests for collection permission classes.

Two permission classes defined in ``permissions.py`` are never attached to any view
(``IsCollectionOwner`` and ``CanViewCollection``), and several branches of the classes that
*are* wired up are defensive checks the viewsets' ``get_queryset`` filtering already makes
unreachable through a real HTTP request - e.g. the "not visible" fallbacks of ``_is_visible``,
or the "not authenticated" checks inside ``has_object_permission`` for unsafe methods, since
``has_permission`` already rejects anonymous requests before object-level permissions run.
These tests exercise those classes and branches directly, rather than through the API.
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from django.contrib.auth.models import AnonymousUser
from model_bakery import baker

from my_game_list.collections.models import CollectionMode, CollectionVisibility
from my_game_list.collections.permissions import (
    CanViewCollection,
    CollectionItemPermission,
    CollectionPermission,
    IsCollectionOwner,
    IsCollectionOwnerOrCollaborator,
)
from my_game_list.friendships.models import Friendship

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

    from my_game_list.collections.models import Collection, CollectionItem
    from my_game_list.users.models import User as UserModel

# `has_object_permission` never reads `view`, so a `None` stand-in is fine at runtime; cast once
# here instead of scattering `type: ignore[arg-type]` over every call site below.
_view = cast("APIView", None)


def _make_request(user: UserModel | AnonymousUser, method: str = "GET") -> Request:
    """Build a minimal request-like object exposing only the attributes permissions read."""
    return cast("Request", SimpleNamespace(user=user, method=method))


# IsCollectionOwner - not attached to any view; exercised directly.


@pytest.mark.django_db()
def test_is_collection_owner_grants_owner(user_fixture: UserModel) -> None:
    """Test that IsCollectionOwner grants access to the collection's owner."""
    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    permission = IsCollectionOwner()
    assert permission.has_object_permission(_make_request(user_fixture), _view, collection) is True


@pytest.mark.django_db()
def test_is_collection_owner_denies_non_owner(user_fixture: UserModel) -> None:
    """Test that IsCollectionOwner denies access to a non-owner."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    permission = IsCollectionOwner()
    assert permission.has_object_permission(_make_request(other_user), _view, collection) is False


# IsCollectionOwnerOrCollaborator - the owner/collaborator-True branches are already covered
# via the reorder-item API tests; these cover the remaining "denied" branches directly.


@pytest.mark.django_db()
def test_owner_or_collaborator_denies_unauthenticated(user_fixture: UserModel) -> None:
    """Test that an unauthenticated request is denied without inspecting ownership."""
    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    permission = IsCollectionOwnerOrCollaborator()
    assert permission.has_object_permission(_make_request(AnonymousUser()), _view, collection) is False


@pytest.mark.django_db()
def test_owner_or_collaborator_denies_non_collaborator_on_non_collaborative_collection(
    user_fixture: UserModel,
) -> None:
    """Test that a non-owner is denied on a non-collaborative collection."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make("collections.Collection", user=user_fixture, mode=CollectionMode.SOLO)
    permission = IsCollectionOwnerOrCollaborator()
    assert permission.has_object_permission(_make_request(other_user), _view, collection) is False


# CanViewCollection - not attached to any view; exercised directly across all its branches.


@pytest.mark.django_db()
def test_can_view_collection_denies_unauthenticated(user_fixture: UserModel) -> None:
    """Test that an unauthenticated viewer is denied."""
    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    permission = CanViewCollection()
    assert permission.has_object_permission(_make_request(AnonymousUser()), _view, collection) is False


@pytest.mark.django_db()
def test_can_view_collection_grants_owner(user_fixture: UserModel) -> None:
    """Test that the owner can always view their own collection."""
    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    permission = CanViewCollection()
    assert permission.has_object_permission(_make_request(user_fixture), _view, collection) is True


@pytest.mark.django_db()
def test_can_view_collection_grants_collaborator(user_fixture: UserModel) -> None:
    """Test that a collaborator can always view the collection."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.PRIVATE,
    )
    collection.collaborators.add(other_user)
    permission = CanViewCollection()
    assert permission.has_object_permission(_make_request(other_user), _view, collection) is True


@pytest.mark.django_db()
def test_can_view_collection_grants_any_authenticated_user_for_public(user_fixture: UserModel) -> None:
    """Test that any authenticated user can view a public collection."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.PUBLIC,
    )
    permission = CanViewCollection()
    assert permission.has_object_permission(_make_request(other_user), _view, collection) is True


@pytest.mark.django_db()
def test_can_view_collection_grants_friend_for_friends_visibility(user_fixture: UserModel) -> None:
    """Test that a friend of the owner can view a FRIENDS-visibility collection."""
    friend: UserModel = baker.make("users.User")
    Friendship.objects.create(user=user_fixture, friend=friend)
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.FRIENDS,
    )
    permission = CanViewCollection()
    assert permission.has_object_permission(_make_request(friend), _view, collection) is True


@pytest.mark.django_db()
def test_can_view_collection_denies_non_member_for_private(user_fixture: UserModel) -> None:
    """Test that an unrelated authenticated user is denied for a private collection."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.PRIVATE,
    )
    permission = CanViewCollection()
    assert permission.has_object_permission(_make_request(other_user), _view, collection) is False


# CollectionPermission._is_visible - the "not visible" fallbacks, unreachable through the API
# because CollectionViewSet.get_queryset already excludes objects a viewer cannot see before
# object-level permissions ever run. Exercised through the public has_object_permission.


@pytest.mark.django_db()
def test_collection_permission_denies_view_for_unauthenticated_non_public(user_fixture: UserModel) -> None:
    """Test that an unauthenticated viewer cannot see a non-public collection."""
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.PRIVATE,
    )
    permission = CollectionPermission()
    assert permission.has_object_permission(_make_request(AnonymousUser()), _view, collection) is False


@pytest.mark.django_db()
def test_collection_permission_denies_view_for_private_non_member(user_fixture: UserModel) -> None:
    """Test that a private, non-friends collection is not visible to an unrelated user."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.PRIVATE,
    )
    permission = CollectionPermission()
    assert permission.has_object_permission(_make_request(other_user), _view, collection) is False


# CollectionItemPermission.has_object_permission - the unsafe-method, non-owner branch.


@pytest.mark.django_db()
def test_collection_item_permission_denies_unauthenticated_unsafe_method(user_fixture: UserModel) -> None:
    """Test that an unauthenticated write request is denied."""
    collection: Collection = baker.make("collections.Collection", user=user_fixture)
    item: CollectionItem = baker.make("collections.CollectionItem", collection=collection)
    permission = CollectionItemPermission()
    request = _make_request(AnonymousUser(), method="PATCH")
    assert permission.has_object_permission(request, _view, item) is False


@pytest.mark.django_db()
def test_collection_item_permission_denies_non_collaborator_unsafe_method(user_fixture: UserModel) -> None:
    """Test that a non-owner, non-collaborator write request is denied."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make("collections.Collection", user=user_fixture, mode=CollectionMode.SOLO)
    item: CollectionItem = baker.make("collections.CollectionItem", collection=collection)
    permission = CollectionItemPermission()
    request = _make_request(other_user, method="PATCH")
    assert permission.has_object_permission(request, _view, item) is False


# CollectionItemPermission._is_visible - same "not visible" fallbacks as above, unreachable
# through the API for the same reason (CollectionItemViewSet.get_queryset pre-filters).


@pytest.mark.django_db()
def test_collection_item_permission_denies_view_for_unauthenticated_non_public(user_fixture: UserModel) -> None:
    """Test that an unauthenticated viewer cannot see an item in a non-public collection."""
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.PRIVATE,
    )
    item: CollectionItem = baker.make("collections.CollectionItem", collection=collection)
    permission = CollectionItemPermission()
    request = _make_request(AnonymousUser())
    assert permission.has_object_permission(request, _view, item) is False


@pytest.mark.django_db()
def test_collection_item_permission_grants_collaborator_view(user_fixture: UserModel) -> None:
    """Test that a collaborator can view an item in a private collaborative collection."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        mode=CollectionMode.COLLABORATIVE,
        visibility=CollectionVisibility.PRIVATE,
    )
    collection.collaborators.add(other_user)
    item: CollectionItem = baker.make("collections.CollectionItem", collection=collection)
    permission = CollectionItemPermission()
    request = _make_request(other_user)
    assert permission.has_object_permission(request, _view, item) is True


@pytest.mark.django_db()
def test_collection_item_permission_grants_friend_view(user_fixture: UserModel) -> None:
    """Test that a friend of the owner can view an item in a FRIENDS-visibility collection."""
    friend: UserModel = baker.make("users.User")
    Friendship.objects.create(user=user_fixture, friend=friend)
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.FRIENDS,
    )
    item: CollectionItem = baker.make("collections.CollectionItem", collection=collection)
    permission = CollectionItemPermission()
    request = _make_request(friend)
    assert permission.has_object_permission(request, _view, item) is True


@pytest.mark.django_db()
def test_collection_item_permission_denies_view_for_private_non_member(user_fixture: UserModel) -> None:
    """Test that an unrelated authenticated user is denied for a private collection's items."""
    other_user: UserModel = baker.make("users.User")
    collection: Collection = baker.make(
        "collections.Collection",
        user=user_fixture,
        visibility=CollectionVisibility.PRIVATE,
    )
    item: CollectionItem = baker.make("collections.CollectionItem", collection=collection)
    permission = CollectionItemPermission()
    request = _make_request(other_user)
    assert permission.has_object_permission(request, _view, item) is False
