"""This module contains the admin model for notification related data."""

from django.contrib import admin

from game_list.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin[Notification]):
    """Admin model for the Notification model."""

    readonly_fields = ("id", "recipient", "actor", "target", "unread", "level", "timestamp")
    search_fields = ("id", "recipient", "actor", "target")
    list_filter = ("unread", "level")
    list_display = (
        *search_fields,
        *list_filter,
        "timestamp",
    )
