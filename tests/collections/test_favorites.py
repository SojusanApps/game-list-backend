"""Tests for per-user collection favorites."""

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

from game_list.collections.models import CollectionFavorite, CollectionVisibility
from game_list.friendships.models import Friendship

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.collections.models import Collection
    from game_list.users.models import User


@pytest.fixture
def owner(user_fixture: User) -> User:
    """The owner of the collections under test."""
    return user_fixture


@pytest.fixture
def other_user() -> User:
    """A user unrelated to the collections under test, unless a test says otherwise."""
    return baker.make("users.User", username="other_user")


def _favorite_url(collection: Collection) -> str:
    return reverse("collections:collections-favorite", args=[collection.id])


def _is_favorite_in_list(api_client: APIClient, collection: Collection) -> bool | None:
    """Return the `is_favorite` the list endpoint reports for a collection, or None if it isn't listed."""
    response = api_client.get(reverse("collections:collections-list"))
    assert response.status_code == status.HTTP_200_OK
    for entry in response.data["results"]:
        if entry["id"] == collection.id:
            return bool(entry["is_favorite"])
    return None


@pytest.mark.django_db()
class TestFavoriteAction:
    """Tests for POST and DELETE on the favorite endpoint."""

    def test_owner_can_favorite_own_collection(self, api_client: APIClient, owner: User) -> None:
        """Test that the owner can favorite their own collection."""
        collection: Collection = baker.make("collections.Collection", user=owner)

        api_client.force_authenticate(owner)
        response = api_client.post(_favorite_url(collection))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert CollectionFavorite.objects.filter(collection=collection, user=owner).exists()

    def test_favoriting_twice_is_idempotent(self, api_client: APIClient, owner: User) -> None:
        """Test that favoriting an already favorited collection succeeds without creating a duplicate."""
        collection: Collection = baker.make("collections.Collection", user=owner)
        api_client.force_authenticate(owner)

        first = api_client.post(_favorite_url(collection))
        second = api_client.post(_favorite_url(collection))

        assert first.status_code == status.HTTP_204_NO_CONTENT
        assert second.status_code == status.HTTP_204_NO_CONTENT
        assert CollectionFavorite.objects.filter(collection=collection, user=owner).count() == 1

    def test_unfavorite_removes_only_own_favorite(self, api_client: APIClient, owner: User, other_user: User) -> None:
        """Test that unfavoriting leaves other users' favorites of the same collection alone."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )
        baker.make("collections.CollectionFavorite", collection=collection, user=owner)
        baker.make("collections.CollectionFavorite", collection=collection, user=other_user)

        api_client.force_authenticate(owner)
        response = api_client.delete(_favorite_url(collection))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CollectionFavorite.objects.filter(collection=collection, user=owner).exists()
        assert CollectionFavorite.objects.filter(collection=collection, user=other_user).exists()

    def test_unfavoriting_a_collection_that_is_not_favorited_is_idempotent(
        self,
        api_client: APIClient,
        owner: User,
    ) -> None:
        """Test that unfavoriting a collection that was never favorited succeeds."""
        collection: Collection = baker.make("collections.Collection", user=owner)

        api_client.force_authenticate(owner)
        response = api_client.delete(_favorite_url(collection))

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_anonymous_visitor_cannot_favorite(self, api_client: APIClient, owner: User) -> None:
        """Test that an anonymous visitor is rejected, even on a PUBLIC collection."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )

        post_response = api_client.post(_favorite_url(collection))
        delete_response = api_client.delete(_favorite_url(collection))

        assert post_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert delete_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not CollectionFavorite.objects.exists()

    def test_viewer_of_public_collection_can_favorite(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
    ) -> None:
        """Test that any user who can see a PUBLIC collection can favorite it without being a collaborator."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )

        api_client.force_authenticate(other_user)
        response = api_client.post(_favorite_url(collection))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert CollectionFavorite.objects.filter(collection=collection, user=other_user).exists()

    def test_friend_can_favorite_friends_collection(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
    ) -> None:
        """Test that a friend of the owner can favorite a FRIENDS collection."""
        Friendship.objects.create(user=other_user, friend=owner)
        Friendship.objects.create(user=owner, friend=other_user)
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.FRIENDS,
        )

        api_client.force_authenticate(other_user)
        response = api_client.post(_favorite_url(collection))

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_collaborator_can_favorite_private_collection(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
    ) -> None:
        """Test that a collaborator can favorite a PRIVATE collection they were added to."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PRIVATE,
        )
        collection.collaborators.add(other_user)

        api_client.force_authenticate(other_user)
        response = api_client.post(_favorite_url(collection))

        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.parametrize("visibility", [CollectionVisibility.PRIVATE, CollectionVisibility.FRIENDS])
    def test_cannot_favorite_collection_that_is_not_visible(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
        visibility: CollectionVisibility,
    ) -> None:
        """Test that a user who can't see a collection gets a 404 and no favorite is created."""
        collection: Collection = baker.make("collections.Collection", user=owner, visibility=visibility)

        api_client.force_authenticate(other_user)
        post_response = api_client.post(_favorite_url(collection))
        delete_response = api_client.delete(_favorite_url(collection))

        assert post_response.status_code == status.HTTP_404_NOT_FOUND
        assert delete_response.status_code == status.HTTP_404_NOT_FOUND
        assert not CollectionFavorite.objects.exists()


@pytest.mark.django_db()
class TestIsFavoriteField:
    """Tests for the per-viewer `is_favorite` response field."""

    def test_owner_favorite_does_not_apply_to_collaborator(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
    ) -> None:
        """Test that the owner favoriting a collection does not favorite it for its collaborators."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PRIVATE,
        )
        collection.collaborators.add(other_user)
        baker.make("collections.CollectionFavorite", collection=collection, user=owner)

        api_client.force_authenticate(owner)
        assert _is_favorite_in_list(api_client, collection) is True

        api_client.force_authenticate(other_user)
        assert _is_favorite_in_list(api_client, collection) is False

    def test_collaborator_favorite_does_not_apply_to_owner(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
    ) -> None:
        """Test that a collaborator's favorite is invisible to the owner."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PRIVATE,
        )
        collection.collaborators.add(other_user)

        api_client.force_authenticate(other_user)
        api_client.post(_favorite_url(collection))
        assert _is_favorite_in_list(api_client, collection) is True

        api_client.force_authenticate(owner)
        assert _is_favorite_in_list(api_client, collection) is False

    def test_owner_favorite_does_not_leak_to_public_viewers(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
    ) -> None:
        """Test that a PUBLIC collection's owner favorite is not shown to strangers or anonymous visitors."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )
        baker.make("collections.CollectionFavorite", collection=collection, user=owner)

        api_client.force_authenticate(other_user)
        assert _is_favorite_in_list(api_client, collection) is False

        api_client.force_authenticate(None)
        assert _is_favorite_in_list(api_client, collection) is False

    def test_retrieve_reports_requesting_users_favorite(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
    ) -> None:
        """Test that the detail endpoint reports the requesting user's own favorite."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )
        baker.make("collections.CollectionFavorite", collection=collection, user=other_user)
        url = reverse("collections:collections-detail", args=[collection.id])

        api_client.force_authenticate(other_user)
        assert api_client.get(url).data["is_favorite"] is True

        api_client.force_authenticate(owner)
        assert api_client.get(url).data["is_favorite"] is False

        api_client.force_authenticate(None)
        assert api_client.get(url).data["is_favorite"] is False

    def test_is_favorite_is_not_writable_on_create(self, api_client: APIClient, owner: User) -> None:
        """Test that `is_favorite` in a create payload is ignored and does not favorite anything."""
        api_client.force_authenticate(owner)
        response = api_client.post(
            reverse("collections:collections-list"),
            {"name": "Payload favorite", "is_favorite": True},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "is_favorite" not in response.data
        assert not CollectionFavorite.objects.exists()

    def test_is_favorite_is_not_writable_on_update(self, api_client: APIClient, owner: User) -> None:
        """Test that `is_favorite` in an update payload is ignored and does not favorite anything."""
        collection: Collection = baker.make("collections.Collection", user=owner)

        api_client.force_authenticate(owner)
        response = api_client.patch(
            reverse("collections:collections-detail", args=[collection.id]),
            {"is_favorite": True},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert not CollectionFavorite.objects.exists()


@pytest.mark.django_db()
class TestIsFavoriteFilter:
    """Tests for the `is_favorite` list filter, which means "favorited by me"."""

    def test_filter_matches_only_own_favorites(self, api_client: APIClient, owner: User, other_user: User) -> None:
        """Test that is_favorite=true/false partition the visible collections by the requester's favorites."""
        favorited: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )
        favorited_by_other: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )
        untouched: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )
        baker.make("collections.CollectionFavorite", collection=favorited, user=other_user)
        baker.make("collections.CollectionFavorite", collection=favorited_by_other, user=owner)
        url = reverse("collections:collections-list")

        api_client.force_authenticate(other_user)
        true_ids = {c["id"] for c in api_client.get(url, {"is_favorite": "true"}).data["results"]}
        false_ids = {c["id"] for c in api_client.get(url, {"is_favorite": "false"}).data["results"]}

        assert true_ids == {favorited.id}
        assert false_ids == {favorited_by_other.id, untouched.id}

    def test_filter_for_anonymous_visitor(self, api_client: APIClient, owner: User) -> None:
        """Test that an anonymous visitor has no favorites: true is empty, false is everything visible."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )
        baker.make("collections.CollectionFavorite", collection=collection, user=owner)
        url = reverse("collections:collections-list")

        true_response = api_client.get(url, {"is_favorite": "true"})
        false_response = api_client.get(url, {"is_favorite": "false"})

        assert true_response.status_code == status.HTTP_200_OK
        assert true_response.data["results"] == []
        assert {c["id"] for c in false_response.data["results"]} == {collection.id}


@pytest.mark.django_db()
class TestFavoriteLifecycle:
    """Tests for what happens to a favorite when access to the collection changes or things are deleted."""

    def test_favorite_is_dormant_while_access_is_lost_and_returns_with_it(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
    ) -> None:
        """Test that losing sight of a collection hides the favorite without deleting it."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PRIVATE,
        )
        collection.collaborators.add(other_user)
        api_client.force_authenticate(other_user)
        api_client.post(_favorite_url(collection))
        detail_url = reverse("collections:collections-detail", args=[collection.id])

        collection.collaborators.remove(other_user)

        assert api_client.get(detail_url).status_code == status.HTTP_404_NOT_FOUND
        assert _is_favorite_in_list(api_client, collection) is None
        assert CollectionFavorite.objects.filter(collection=collection, user=other_user).exists()

        collection.collaborators.add(other_user)

        assert _is_favorite_in_list(api_client, collection) is True

    def test_deleting_collection_deletes_its_favorites(self, owner: User, other_user: User) -> None:
        """Test that favorites are removed along with their collection."""
        collection: Collection = baker.make("collections.Collection", user=owner)
        baker.make("collections.CollectionFavorite", collection=collection, user=other_user)

        collection.delete()

        assert not CollectionFavorite.objects.exists()

    def test_deleting_user_deletes_their_favorites_only(self, owner: User, other_user: User) -> None:
        """Test that erasing a user removes their favorites but not the owner's favorite of the same collection."""
        collection: Collection = baker.make(
            "collections.Collection",
            user=owner,
            visibility=CollectionVisibility.PUBLIC,
        )
        baker.make("collections.CollectionFavorite", collection=collection, user=owner)
        baker.make("collections.CollectionFavorite", collection=collection, user=other_user)

        other_user.delete()

        assert list(CollectionFavorite.objects.values_list("user_id", flat=True)) == [owner.id]
