"""This module contains the admin model for the friendship related data."""

from django.contrib import admin

from game_list.friendships.models import Friendship, FriendshipRequest


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin[Friendship]):
    """Admin model for the friendship model."""

    readonly_fields = ("id", "created_at")
    search_fields = (*readonly_fields, "user__username")
    raw_id_fields = (
        "user",
        "friend",
    )
    list_display = (*readonly_fields, *raw_id_fields)


@admin.register(FriendshipRequest)
class FriendshipRequestAdmin(admin.ModelAdmin[FriendshipRequest]):
    """Admin model for the friendship request model."""

    readonly_fields = ("id",)
    search_fields = (*readonly_fields, "sender__username", "receiver__username")
    raw_id_fields = ("sender", "receiver")
    list_filter = ("created_at", "last_modified_at", "rejected_at")
    list_display = (*readonly_fields, *list_filter, *raw_id_fields)
