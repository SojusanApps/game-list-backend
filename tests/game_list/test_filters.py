"""Tests for base lookup model filters."""

import pytest
from django import forms as django_forms
from model_bakery import baker

from game_list.game_list.filters import BilingualModelMultipleChoiceField
from game_list.games.filters import GenreFilterSet
from game_list.games.models import Genre


@pytest.mark.django_db()
def test_bilingual_field_resolves_values_by_english_or_polish_name() -> None:
    """A value matching either the English or Polish name (case-insensitively) resolves to that record."""
    action = baker.make(Genre, name_en="Action", name_pl="Akcja")
    adventure = baker.make(Genre, name_en="Adventure", name_pl="Przygoda")
    field = BilingualModelMultipleChoiceField(queryset=Genre.objects.all())

    resolved = field.clean(["action", "przygoda"])

    assert set(resolved) == {action, adventure}


@pytest.mark.django_db()
def test_bilingual_field_raises_for_an_unmatched_value() -> None:
    """A value that matches neither the English nor Polish name of any record is an invalid choice."""
    baker.make(Genre, name_en="Action", name_pl="Akcja")
    field = BilingualModelMultipleChoiceField(queryset=Genre.objects.all())

    with pytest.raises(django_forms.ValidationError):
        field.clean(["Nonexistent Genre"])


@pytest.mark.django_db()
def test_base_lookup_filter_set_filters_name_by_english_or_polish() -> None:
    """BaseLookupFilterSet.filter_name matches partial, case-insensitive hits in either language."""
    matching = baker.make(Genre, name_en="Role-playing", name_pl="RPG")
    baker.make(Genre, name_en="Shooter", name_pl="Strzelanka")

    filter_set = GenreFilterSet(data={"name": "rpg"}, queryset=Genre.objects.all())

    assert list(filter_set.qs) == [matching]
