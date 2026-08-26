"""Tests for collection types and validation."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker

from game_list.collections.models import Collection, CollectionItem, CollectionType

if TYPE_CHECKING:
    from game_list.games.models import Game
    from game_list.users.models import User


@pytest.mark.django_db()
def test_collection_type_choices() -> None:
    """Test that CollectionType has the expected choices."""
    assert CollectionType.NORMAL.value == "NOR"
    assert CollectionType.RANK.value == "RNK"
    assert CollectionType.TIER.value == "TIE"


@pytest.mark.django_db()
def test_collection_default_type(collection_fixture: Collection) -> None:
    """Test that Collection has NORMAL type by default."""
    assert collection_fixture.type == CollectionType.NORMAL


@pytest.mark.django_db()
def test_rank_collection_allows_empty_order() -> None:
    """Test that a rank collection allows empty order for its items initially."""
    user: User = baker.make("users.User")
    collection = Collection.objects.create(name="Ranked", user=user, type=CollectionType.RANK)
    game: Game = baker.make("games.Game")

    item = CollectionItem(collection=collection, game=game, order=None)
    item.clean()  # Should not raise ValidationError


@pytest.mark.django_db()
def test_tier_collection_allows_empty_tier() -> None:
    """Test that a tier collection allows empty tier for its items initially."""
    user: User = baker.make("users.User")
    collection = Collection.objects.create(name="Tiers", user=user, type=CollectionType.TIER)
    game: Game = baker.make("games.Game")

    item = CollectionItem(collection=collection, game=game, tier="")
    item.clean()  # Should not raise ValidationError


@pytest.mark.django_db()
def test_normal_collection_validation_passes() -> None:
    """Test that a normal collection validation passes with empty order/tier."""
    user: User = baker.make("users.User")
    collection = Collection.objects.create(name="Normal", user=user, type=CollectionType.NORMAL)
    game: Game = baker.make("games.Game")

    item = CollectionItem(collection=collection, game=game, order=None, tier="")
    item.clean()  # Should not raise ValidationError
