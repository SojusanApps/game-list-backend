"""This module contains the configuration for user application."""

import contextlib

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Configuration for the users application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "game_list.users"

    def ready(self) -> None:
        """Import signals when the app is ready."""
        with contextlib.suppress(ImportError):
            import game_list.users.signals  # noqa: F401, PLC0415
