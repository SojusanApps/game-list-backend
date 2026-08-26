"""This module contains the configuration for the game application."""

import contextlib

from django.apps import AppConfig


class GamesConfig(AppConfig):
    """Configuration for the games application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "game_list.games"

    def ready(self) -> None:
        """Import signals when the app is ready."""
        with contextlib.suppress(ImportError):
            import game_list.games.signals  # noqa: F401, PLC0415
