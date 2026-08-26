"""Tests for the shared unique-slug generation helper."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker

from game_list.collections.models import Collection
from game_list.game_list.slugs import generate_unique_slug

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_generate_unique_slug_no_collision() -> None:
    """When nothing else has the base slug, it's returned unchanged."""
    assert generate_unique_slug(Collection, "My Favorites") == "my-favorites"


@pytest.mark.django_db()
def test_generate_unique_slug_single_collision(user_fixture: UserModel) -> None:
    """When the base slug is already taken, a `-1` suffix is appended."""
    baker.make(Collection, user=user_fixture, slug="my-favorites")

    assert generate_unique_slug(Collection, "My Favorites") == "my-favorites-1"


@pytest.mark.django_db()
def test_generate_unique_slug_multiple_collisions(user_fixture: UserModel) -> None:
    """When the base slug and its `-1` suffix are both taken, `-2` is used."""
    baker.make(Collection, user=user_fixture, slug="my-favorites")
    baker.make(Collection, user=user_fixture, slug="my-favorites-1")

    assert generate_unique_slug(Collection, "My Favorites") == "my-favorites-2"


@pytest.mark.django_db()
def test_generate_unique_slug_excludes_own_pk(user_fixture: UserModel) -> None:
    """An instance's own existing row isn't treated as a collision against itself."""
    collection = baker.make(Collection, user=user_fixture, slug="my-favorites")

    assert generate_unique_slug(Collection, "My Favorites", exclude_pk=collection.pk) == "my-favorites"
