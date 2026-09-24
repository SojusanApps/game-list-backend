"""Tests for collections models."""

from typing import TYPE_CHECKING

import pytest
from django.db import IntegrityError
from model_bakery import baker

from game_list.collections.models import (
    Collection,
    CollectionFavorite,
    CollectionItem,
    CollectionMode,
    CollectionVisibility,
    Tier,
)

if TYPE_CHECKING:
    from game_list.games.models import Game
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_collection_dunder_str(collection_fixture: Collection) -> None:
    """Test the `Collection` dunder str method."""
    assert str(collection_fixture) == f"{collection_fixture.user.username} - {collection_fixture.name}"


@pytest.mark.django_db()
def test_collection_favorite_dunder_str(collection_fixture: Collection, admin_user_fixture: UserModel) -> None:
    """Test the `CollectionFavorite` dunder str method."""
    favorite = CollectionFavorite.objects.create(collection=collection_fixture, user=admin_user_fixture)
    assert str(favorite) == f"{admin_user_fixture.username} - {collection_fixture.name}"


@pytest.mark.django_db()
def test_collection_favorite_unique_constraint(collection_fixture: Collection, admin_user_fixture: UserModel) -> None:
    """Test that a user can favorite a given collection only once."""
    CollectionFavorite.objects.create(collection=collection_fixture, user=admin_user_fixture)

    with pytest.raises(IntegrityError):
        CollectionFavorite.objects.create(collection=collection_fixture, user=admin_user_fixture)


@pytest.mark.django_db()
def test_collection_item_dunder_str(collection_item_fixture: CollectionItem) -> None:
    """Test the `CollectionItem` dunder str method."""
    collection_name = collection_item_fixture.collection.name
    game_title = collection_item_fixture.game.title
    order = collection_item_fixture.order
    expected = f"{collection_name} - {game_title} (#{order})"
    assert str(collection_item_fixture) == expected


@pytest.mark.django_db()
def test_collection_visibility_choices() -> None:
    """Test that CollectionVisibility has the expected choices."""
    assert CollectionVisibility.PUBLIC == "PUB"  # type: ignore[comparison-overlap]
    assert CollectionVisibility.FRIENDS == "FRI"  # type: ignore[comparison-overlap]
    assert CollectionVisibility.PRIVATE == "PRI"  # type: ignore[comparison-overlap]


@pytest.mark.django_db()
def test_collection_mode_choices() -> None:
    """Test that CollectionMode has the expected choices."""
    assert CollectionMode.SOLO == "S"  # type: ignore[comparison-overlap]
    assert CollectionMode.COLLABORATIVE == "C"  # type: ignore[comparison-overlap]


@pytest.mark.django_db()
def test_tier_choices() -> None:
    """Test that Tier has the expected choices."""
    assert Tier.S == "S"
    assert Tier.A == "A"
    assert Tier.B == "B"
    assert Tier.C == "C"
    assert Tier.D == "D"
    assert Tier.E == "E"
    assert Tier.F == "F"


@pytest.mark.django_db()
def test_collection_default_values(collection_fixture: Collection) -> None:
    """Test that Collection has expected default values."""
    assert collection_fixture.visibility == CollectionVisibility.PRIVATE
    assert collection_fixture.mode == CollectionMode.SOLO


@pytest.mark.django_db()
def test_collection_item_unique_constraint(
    collection_fixture: Collection,
    collection_item_fixture: CollectionItem,
) -> None:
    """Test that the same game cannot be added twice to a collection."""
    with pytest.raises(IntegrityError):
        CollectionItem.objects.create(
            order=2,
            collection=collection_fixture,
            game=collection_item_fixture.game,
        )


@pytest.mark.django_db()
def test_collection_item_without_tier(collection_fixture: Collection) -> None:
    """Test that collection item can be created without a tier."""
    game: Game = baker.make("games.Game")
    item = CollectionItem.objects.create(
        order=1,
        tier="",
        collection=collection_fixture,
        game=game,
    )
    assert item.tier == ""


@pytest.mark.django_db()
def test_collection_collaborators(collection_fixture: Collection, admin_user_fixture: UserModel) -> None:
    """Test that collaborators can be added to a collection."""
    collection_fixture.collaborators.add(admin_user_fixture)
    assert collection_fixture.collaborators.count() == 1
    assert admin_user_fixture in collection_fixture.collaborators.all()


@pytest.mark.django_db()
def test_collection_slug_generation(admin_user_fixture: UserModel) -> None:
    """Test that saving a collection generates a correct and unique slug."""
    first_collection: Collection = baker.make(
        Collection,
        name="My Favorites",
        user=admin_user_fixture,
        slug="",
    )
    assert first_collection.slug == f"{admin_user_fixture.username}-my-favorites"

    second_collection: Collection = baker.make(
        Collection,
        name="My Favorites",
        user=admin_user_fixture,
        slug="",
    )
    assert second_collection.slug == f"{admin_user_fixture.username}-my-favorites-1"

    third_collection: Collection = baker.make(
        Collection,
        name="My Favorites",
        user=admin_user_fixture,
        slug="",
    )
    assert third_collection.slug == f"{admin_user_fixture.username}-my-favorites-2"
