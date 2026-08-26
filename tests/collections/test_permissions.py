"""Tests for collection permissions."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status

from game_list.collections.models import Collection, CollectionItem, CollectionMode, CollectionVisibility
from game_list.friendships.models import Friendship

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.fixture
def other_user_fixture() -> UserModel:
    """Create another user for permission testing."""
    return baker.make(User, username="other_user")


@pytest.fixture
def friend_user_fixture(user_fixture: UserModel) -> UserModel:
    """Create a friend user and establish friendship."""
    friend = baker.make(User, username="friend_user")
    # Create bidirectional friendship
    Friendship.objects.create(user=user_fixture, friend=friend)
    Friendship.objects.create(user=friend, friend=user_fixture)
    return friend


@pytest.fixture
def private_collection_fixture(user_fixture: UserModel) -> Collection:
    """Create a private collection."""
    return Collection.objects.create(
        name="Private Collection",
        visibility=CollectionVisibility.PRIVATE,
        mode=CollectionMode.SOLO,
        user=user_fixture,
    )


@pytest.fixture
def public_collection_fixture(user_fixture: UserModel) -> Collection:
    """Create a public collection."""
    return Collection.objects.create(
        name="Public Collection",
        visibility=CollectionVisibility.PUBLIC,
        mode=CollectionMode.SOLO,
        user=user_fixture,
    )


@pytest.fixture
def friends_collection_fixture(user_fixture: UserModel) -> Collection:
    """Create a friends-only collection."""
    return Collection.objects.create(
        name="Friends Collection",
        visibility=CollectionVisibility.FRIENDS,
        mode=CollectionMode.SOLO,
        user=user_fixture,
    )


@pytest.fixture
def collaborative_collection_fixture(user_fixture: UserModel, other_user_fixture: UserModel) -> Collection:
    """Create a collaborative collection with a collaborator."""
    collection = Collection.objects.create(
        name="Collaborative Collection",
        visibility=CollectionVisibility.PRIVATE,
        mode=CollectionMode.COLLABORATIVE,
        user=user_fixture,
    )
    collection.collaborators.add(other_user_fixture)
    return collection


# Collection Visibility Tests


@pytest.mark.django_db()
def test_owner_can_view_private_collection(
    authenticated_api_client: APIClient,
    private_collection_fixture: Collection,
) -> None:
    """Test that owner can view their private collection."""
    response = authenticated_api_client.get(f"/api/collection/collections/{private_collection_fixture.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_other_user_cannot_view_private_collection(
    api_client: APIClient,
    private_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that other users cannot view private collections."""
    api_client.force_authenticate(other_user_fixture)
    response = api_client.get(f"/api/collection/collections/{private_collection_fixture.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db()
def test_anyone_can_view_public_collection(
    api_client: APIClient,
    public_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that any authenticated user can view public collections."""
    api_client.force_authenticate(other_user_fixture)
    response = api_client.get(f"/api/collection/collections/{public_collection_fixture.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_friend_can_view_friends_collection(
    api_client: APIClient,
    friends_collection_fixture: Collection,
    friend_user_fixture: UserModel,
) -> None:
    """Test that friends can view friends-only collections."""
    api_client.force_authenticate(friend_user_fixture)
    response = api_client.get(f"/api/collection/collections/{friends_collection_fixture.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_non_friend_cannot_view_friends_collection(
    api_client: APIClient,
    friends_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that non-friends cannot view friends-only collections."""
    api_client.force_authenticate(other_user_fixture)
    response = api_client.get(f"/api/collection/collections/{friends_collection_fixture.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Collection Modification Tests


@pytest.mark.django_db()
def test_owner_can_update_collection(
    authenticated_api_client: APIClient,
    private_collection_fixture: Collection,
) -> None:
    """Test that owner can update their collection."""
    response = authenticated_api_client.patch(
        f"/api/collection/collections/{private_collection_fixture.id}/",
        {"name": "Updated Name"},
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_other_user_cannot_update_collection(
    api_client: APIClient,
    public_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that other users cannot update collections they don't own."""
    api_client.force_authenticate(other_user_fixture)
    response = api_client.patch(
        f"/api/collection/collections/{public_collection_fixture.id}/",
        {"name": "Hacked Name"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db()
def test_owner_can_delete_collection(
    authenticated_api_client: APIClient,
    private_collection_fixture: Collection,
) -> None:
    """Test that owner can delete their collection."""
    response = authenticated_api_client.delete(f"/api/collection/collections/{private_collection_fixture.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db()
def test_collaborator_cannot_delete_collection(
    api_client: APIClient,
    collaborative_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that collaborators cannot delete collections."""
    api_client.force_authenticate(other_user_fixture)
    response = api_client.delete(f"/api/collection/collections/{collaborative_collection_fixture.id}/")
    assert response.status_code == status.HTTP_403_FORBIDDEN


# Collaborator Tests


@pytest.mark.django_db()
def test_collaborator_can_view_private_collection(
    api_client: APIClient,
    collaborative_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that collaborators can view private collaborative collections."""
    api_client.force_authenticate(other_user_fixture)
    response = api_client.get(f"/api/collection/collections/{collaborative_collection_fixture.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_collaborator_can_add_item_to_collaborative_collection(
    api_client: APIClient,
    collaborative_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that collaborators can add items to collaborative collections."""
    game: Game = baker.make("games.Game")
    api_client.force_authenticate(other_user_fixture)
    response = api_client.post(
        "/api/collection/collection-items/",
        {
            "collection": collaborative_collection_fixture.id,
            "game": game.id,
            "order": 1,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db()
def test_non_collaborator_cannot_add_item_to_collaborative_collection(
    api_client: APIClient,
    collaborative_collection_fixture: Collection,
) -> None:
    """Test that a non-collaborator cannot add items even to a collaborative collection."""
    game: Game = baker.make("games.Game")
    non_collaborator: UserModel = baker.make(User, username="non_collaborator")
    api_client.force_authenticate(non_collaborator)
    response = api_client.post(
        "/api/collection/collection-items/",
        {
            "collection": collaborative_collection_fixture.id,
            "game": game.id,
            "order": 1,
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db()
def test_non_collaborator_cannot_add_item_to_solo_collection(
    api_client: APIClient,
    public_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that non-collaborators cannot add items to solo collections."""
    game: Game = baker.make("games.Game")
    api_client.force_authenticate(other_user_fixture)
    response = api_client.post(
        "/api/collection/collection-items/",
        {
            "collection": public_collection_fixture.id,
            "game": game.id,
            "order": 1,
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


# Collection List Filtering Tests


@pytest.mark.django_db()
def test_collection_list_excludes_others_private_collections(
    api_client: APIClient,
    private_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that private collections don't appear in other users' list."""
    api_client.force_authenticate(other_user_fixture)
    response = api_client.get("/api/collection/collections/")
    assert response.status_code == status.HTTP_200_OK
    collection_ids = [c["id"] for c in response.data["results"]]
    assert private_collection_fixture.id not in collection_ids


@pytest.mark.django_db()
def test_collection_list_includes_public_collections(
    api_client: APIClient,
    public_collection_fixture: Collection,
    other_user_fixture: UserModel,
) -> None:
    """Test that public collections appear in other users' list."""
    api_client.force_authenticate(other_user_fixture)
    response = api_client.get("/api/collection/collections/")
    assert response.status_code == status.HTTP_200_OK
    collection_ids = [c["id"] for c in response.data["results"]]
    assert public_collection_fixture.id in collection_ids


# Anonymous (Unauthenticated) Visitor Tests


@pytest.mark.django_db()
def test_anonymous_can_view_public_collection(
    api_client: APIClient,
    public_collection_fixture: Collection,
) -> None:
    """Test that a fully anonymous visitor can view a public collection."""
    response = api_client.get(f"/api/collection/collections/{public_collection_fixture.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_anonymous_cannot_view_private_collection(
    api_client: APIClient,
    private_collection_fixture: Collection,
) -> None:
    """Test that an anonymous visitor cannot view a private collection."""
    response = api_client.get(f"/api/collection/collections/{private_collection_fixture.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db()
def test_anonymous_cannot_view_friends_collection(
    api_client: APIClient,
    friends_collection_fixture: Collection,
) -> None:
    """Test that an anonymous visitor cannot view a friends-only collection - they can never be a friend."""
    response = api_client.get(f"/api/collection/collections/{friends_collection_fixture.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db()
def test_anonymous_collection_list_only_includes_public(
    api_client: APIClient,
    private_collection_fixture: Collection,
    public_collection_fixture: Collection,
    friends_collection_fixture: Collection,
) -> None:
    """Test that an anonymous visitor's collection listing only contains PUBLIC collections."""
    response = api_client.get("/api/collection/collections/")
    assert response.status_code == status.HTTP_200_OK
    collection_ids = {c["id"] for c in response.data["results"]}
    assert collection_ids == {public_collection_fixture.id}
    assert private_collection_fixture.id not in collection_ids
    assert friends_collection_fixture.id not in collection_ids


@pytest.mark.django_db()
def test_anonymous_cannot_update_public_collection(
    api_client: APIClient,
    public_collection_fixture: Collection,
) -> None:
    """Test that an anonymous visitor cannot update a collection, even a public one."""
    response = api_client.patch(
        f"/api/collection/collections/{public_collection_fixture.id}/",
        {"name": "Hacked Name"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_anonymous_can_view_item_in_public_collection(
    api_client: APIClient,
    public_collection_fixture: Collection,
) -> None:
    """Test that an anonymous visitor can view an item inside a public collection."""
    game: Game = baker.make("games.Game")
    item = CollectionItem.objects.create(
        order=1,
        collection=public_collection_fixture,
        game=game,
        added_by=public_collection_fixture.user,
    )
    response = api_client.get(f"/api/collection/collection-items/{item.id}/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
def test_anonymous_cannot_view_item_in_private_collection(
    api_client: APIClient,
    private_collection_fixture: Collection,
) -> None:
    """Test that an anonymous visitor cannot view an item inside a private collection."""
    game: Game = baker.make("games.Game")
    item = CollectionItem.objects.create(
        order=1,
        collection=private_collection_fixture,
        game=game,
        added_by=private_collection_fixture.user,
    )
    response = api_client.get(f"/api/collection/collection-items/{item.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db()
def test_anonymous_cannot_create_collection_item(
    api_client: APIClient,
    public_collection_fixture: Collection,
) -> None:
    """Test that an anonymous visitor cannot add an item to any collection, even a public one."""
    game: Game = baker.make("games.Game")
    response = api_client.post(
        "/api/collection/collection-items/",
        {
            "collection": public_collection_fixture.id,
            "game": game.id,
            "order": 1,
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
