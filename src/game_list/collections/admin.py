"""This module contains the admin models for collection related data."""

from django.contrib import admin

from game_list.collections.models import Collection, CollectionFavorite, CollectionItem


class CollectionItemInline(admin.TabularInline[CollectionItem, Collection]):
    """Inline admin for collection items."""

    model = CollectionItem
    extra = 0
    readonly_fields = ("id", "created_at", "last_modified_at")
    raw_id_fields = ("game", "added_by")


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin[Collection]):
    """Admin model for the collection model."""

    readonly_fields = ("id", "created_at", "last_modified_at")
    search_fields = ("id", "name", "user__username")
    raw_id_fields = ("user",)
    list_filter = ("visibility", "mode", "created_at", "last_modified_at")
    list_display = ("id", "name", "user", "visibility", "mode", "created_at")
    filter_horizontal = ("collaborators",)
    inlines = (CollectionItemInline,)


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin[CollectionItem]):
    """Admin model for the collection item model."""

    readonly_fields = ("id", "created_at", "last_modified_at")
    search_fields = ("id", "collection__name", "game__title", "added_by__username")
    raw_id_fields = ("collection", "game", "added_by")
    list_filter = ("tier", "created_at", "last_modified_at")
    list_display = ("id", "collection", "game", "order", "tier", "added_by", "created_at")


@admin.register(CollectionFavorite)
class CollectionFavoriteAdmin(admin.ModelAdmin[CollectionFavorite]):
    """Admin model for the collection favorite model."""

    readonly_fields = ("id", "created_at")
    search_fields = ("id", "collection__name", "user__username")
    raw_id_fields = ("collection", "user")
    list_filter = ("created_at",)
    list_display = ("id", "collection", "user", "created_at")
