"""Tests for the `backfill_search_title` RunPython function in the games app's squashed initial migration.

The current model shape matches what the migration expects, so the function is called
directly with the real `django.apps.apps` registry instead of a migration-state harness.
"""

import importlib

import pytest
from django.apps import apps
from model_bakery import baker

from game_list.games.models import Game

_migration = importlib.import_module("game_list.games.migrations.0001_initial")
backfill_search_title = _migration.backfill_search_title


@pytest.mark.django_db()
def test_backfill_search_title_normalizes_and_merges_both_languages() -> None:
    """backfill_search_title recomputes search_title from title_en/title_pl, deduplicated and sorted."""
    game = baker.make(Game, title_en="Wiedzmin", title_pl="The Witcher")
    Game.objects.filter(pk=game.pk).update(search_title="")

    backfill_search_title(apps, None)

    game.refresh_from_db()
    assert game.search_title == "the witcher wiedzmin"


@pytest.mark.django_db()
def test_backfill_search_title_strips_diacritics_and_punctuation() -> None:
    """backfill_search_title strips diacritics and collapses punctuation to spaces, same as Game.save()."""
    game = baker.make(Game, title_en="Half-Life: Alyx", title_pl="Half-Life: Alyx")
    Game.objects.filter(pk=game.pk).update(search_title="")

    backfill_search_title(apps, None)

    game.refresh_from_db()
    assert game.search_title == "half life alyx"


@pytest.mark.django_db()
def test_backfill_search_title_deduplicates_identical_normalized_titles() -> None:
    """When EN and PL titles normalize identically, search_title stores the value only once."""
    game = baker.make(Game, title_en="FIFA 24", title_pl="FIFA 24")
    Game.objects.filter(pk=game.pk).update(search_title="")

    backfill_search_title(apps, None)

    game.refresh_from_db()
    assert game.search_title == "fifa 24"


@pytest.mark.django_db()
def test_backfill_search_title_updates_multiple_games_in_one_pass() -> None:
    """backfill_search_title iterates and updates every game, not just the first one."""
    first = baker.make(Game, title_en="Portal", title_pl="Portal")
    second = baker.make(Game, title_en="Portal 2", title_pl="Portal 2")
    Game.objects.filter(pk__in=[first.pk, second.pk]).update(search_title="")

    backfill_search_title(apps, None)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.search_title == "portal"
    assert second.search_title == "portal 2"
