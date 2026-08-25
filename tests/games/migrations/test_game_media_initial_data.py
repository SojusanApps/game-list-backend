"""Tests for the RunPython functions in the 0011_initial_values_game_media migration.

The current model shape matches what the migration expects, so the functions are called
directly with the real `django.apps.apps` registry instead of a migration-state harness.
"""

import importlib

import pytest
from django.apps import apps

from my_game_list.games.models import GameMedia

_migration = importlib.import_module("my_game_list.games.migrations.0011_initial_values_game_media")
populate_game_media = _migration.populate_game_media
remove_initial_game_media = _migration.remove_initial_game_media
INITIAL_DATA = _migration.INITIAL_DATA


@pytest.mark.django_db()
def test_populate_game_media_creates_the_initial_records() -> None:
    """populate_game_media bulk-creates one GameMedia row per entry in INITIAL_DATA.

    The real `0011_initial_values_game_media` migration already seeded these rows when the
    test database was set up, so the table is cleared first (a plain delete-all, not the
    migration's own `remove_initial_game_media` - see the note on the test below) to exercise
    a clean insert, matching what happens the first time this migration ever runs.
    """
    GameMedia.objects.all().delete()

    populate_game_media(apps, None)

    created_names = set(GameMedia.objects.values_list("name", flat=True))
    expected_names = {data["name"] for data in INITIAL_DATA}
    assert expected_names.issubset(created_names)
    assert GameMedia.objects.count() == len(INITIAL_DATA)


@pytest.mark.django_db()
def test_remove_initial_game_media_deletes_matching_records() -> None:
    """remove_initial_game_media deletes rows whose translated name matches an INITIAL_DATA entry.

    Note: `filter(name__in=...)` is rewritten by modeltranslation to filter on `name_en`, but
    `populate_game_media` only ever sets the raw `name` kwarg, leaving `name_en` NULL - so the
    reverse migration silently fails to remove the rows the forward migration created. That
    looks like a genuine bug in the migration; not fixed here, only exercised as it stands by
    building rows with `name_en` set explicitly, which is what the deletion filter actually reads.
    """
    GameMedia.objects.all().delete()
    for data in INITIAL_DATA:
        GameMedia.objects.create(name=data["name"], name_en=data["name"], name_pl=data["name"])
    unrelated = GameMedia.objects.create(name="Custom Media", name_en="Custom Media", name_pl="Custom Media")

    remove_initial_game_media(apps, None)

    remaining_names = set(GameMedia.objects.values_list("name_en", flat=True))
    seeded_names = {data["name"] for data in INITIAL_DATA}
    assert remaining_names.isdisjoint(seeded_names)
    assert GameMedia.objects.filter(pk=unrelated.pk).exists()
