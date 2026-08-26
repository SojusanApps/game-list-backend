"""This module contains the base model class for all admin lookup models."""

from typing import ClassVar

from modeltranslation.admin import TabbedTranslationAdmin

from game_list.game_list.models import BaseLookupModel


class BaseLookupModelAdmin(TabbedTranslationAdmin[BaseLookupModel]):
    """Base admin model for lookup."""

    readonly_fields: ClassVar[tuple[str, ...]] = ("id",)
    search_fields: ClassVar[tuple[str, ...]] = ("name_en", "name_pl")
    list_display: tuple[str, ...] = (*readonly_fields, *search_fields)
