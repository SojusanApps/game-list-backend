"""This module contains the configuration for the collections application."""

from django.apps import AppConfig


class CollectionsConfig(AppConfig):
    """Configuration for the collections application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "game_list.collections"
