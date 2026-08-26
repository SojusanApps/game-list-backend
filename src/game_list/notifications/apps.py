"""This module contains the configuration for the notification application."""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Configuration for the notifications application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "game_list.notifications"
