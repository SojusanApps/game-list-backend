"""The fixtures used within collections test module."""

from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time
from model_bakery import baker

from game_list.collections.models import (
    Collection,
    CollectionItem,
    CollectionMode,
    CollectionVisibility,
    Tier,
)

if TYPE_CHECKING:
    from game_list.games.models import Game
    from game_list.users.models import User as UserModel


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def collections_game_fixture() -> Game:
    """A fixture with a test game for collections tests."""
    return baker.make("games.Game")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def collection_fixture(user_fixture: UserModel) -> Collection:
    """A fixture with a test collection."""
    return Collection.objects.create(
        name="Test Collection",
        description="A test collection for testing.",
        is_favorite=False,
        visibility=CollectionVisibility.PRIVATE,
        mode=CollectionMode.SOLO,
        user=user_fixture,
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def public_collection_fixture(user_fixture: UserModel) -> Collection:
    """A fixture with a public test collection."""
    return Collection.objects.create(
        name="Public Test Collection",
        description="A public test collection.",
        is_favorite=True,
        visibility=CollectionVisibility.PUBLIC,
        mode=CollectionMode.SOLO,
        user=user_fixture,
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def collaborative_collection_fixture(user_fixture: UserModel) -> Collection:
    """A fixture with a collaborative test collection."""
    return Collection.objects.create(
        name="Collaborative Collection",
        description="A collaborative test collection.",
        is_favorite=False,
        visibility=CollectionVisibility.FRIENDS,
        mode=CollectionMode.COLLABORATIVE,
        user=user_fixture,
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def collection_item_fixture(
    collection_fixture: Collection,
    collections_game_fixture: Game,
    user_fixture: UserModel,
) -> CollectionItem:
    """A fixture with a test collection item."""
    return CollectionItem.objects.create(
        order=1,
        tier=Tier.S,
        description="Best game ever!",
        collection=collection_fixture,
        game=collections_game_fixture,
        added_by=user_fixture,
    )
