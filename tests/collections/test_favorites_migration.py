"""Tests for the migration that moves `Collection.is_favorite` into per-user favorites."""

from typing import TYPE_CHECKING, Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

if TYPE_CHECKING:
    from django.apps.registry import Apps

_BEFORE = [("collections", "0001_initial")]
_AFTER = [("collections", "0002_per_user_collection_favorites")]


def _migrate(targets: list[tuple[str, str]]) -> Apps:
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return MigrationExecutor(connection).loader.project_state(targets).apps


@pytest.mark.django_db(transaction=True)
def test_migration_favorites_flagged_collections_for_their_owners_and_reverses() -> None:
    """Test the forward data copy, and that reversing restores the owner-level flag from owner favorites only."""
    old_apps = _migrate(_BEFORE)
    user_model: Any = old_apps.get_model("users", "User")
    collection_model: Any = old_apps.get_model("collections", "Collection")
    owner = user_model.objects.create(username="migration_owner", slug="migration-owner", email="owner@example.com")
    collaborator = user_model.objects.create(
        username="migration_collaborator",
        slug="migration-collaborator",
        email="collaborator@example.com",
    )
    flagged = collection_model.objects.create(name="Flagged", slug="flagged", user=owner, is_favorite=True)
    plain = collection_model.objects.create(name="Plain", slug="plain", user=owner, is_favorite=False)
    flagged.collaborators.add(collaborator)

    try:
        favorite_model = _migrate(_AFTER).get_model("collections", "CollectionFavorite")

        # Only the owner's flag becomes a favorite; the collaborator starts with none.
        assert list(favorite_model.objects.values_list("collection_id", "user_id")) == [(flagged.id, owner.id)]

        # Reversing restores the flag from the owner's favorite.
        collection_model = _migrate(_BEFORE).get_model("collections", "Collection")
        assert set(collection_model.objects.filter(is_favorite=True).values_list("id", flat=True)) == {flagged.id}

        # A collaborator's favorite has no equivalent in the old model, so it must not flag the collection.
        favorite_model = _migrate(_AFTER).get_model("collections", "CollectionFavorite")
        favorite_model.objects.all().delete()
        favorite_model.objects.create(collection_id=plain.id, user_id=collaborator.id)
        collection_model = _migrate(_BEFORE).get_model("collections", "Collection")
        assert not collection_model.objects.filter(is_favorite=True).exists()
    finally:
        _migrate(_AFTER)
