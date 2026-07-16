"""This module contains the models for the collection related data."""

from typing import Any, ClassVar, Self

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from my_game_list.my_game_list.models import BaseModel
from my_game_list.my_game_list.slugs import generate_unique_slug


class CollectionVisibility(models.TextChoices):
    """Visibility options for collections."""

    PUBLIC = "PUB", _("Public")
    FRIENDS = "FRI", _("Friends only")
    PRIVATE = "PRI", _("Private")


class CollectionMode(models.TextChoices):
    """Mode options for collections."""

    SOLO = "S", _("Solo")
    COLLABORATIVE = "C", _("Collaborative")


class CollectionType(models.TextChoices):
    """Type options for collections."""

    NORMAL = "NOR", _("Normal")
    RANK = "RNK", _("Ranking")
    TIER = "TIE", _("Tier list")


class Tier(models.TextChoices):
    """Tier options for collection items."""

    S = "S", _("S Tier")
    A = "A", _("A Tier")
    B = "B", _("B Tier")
    C = "C", _("C Tier")
    D = "D", _("D Tier")
    E = "E", _("E Tier")


class Collection(BaseModel):
    """A model representing a game collection.

    A collection is a curated list of games that users can create to organize
    games by theme, ranking, or any other criteria. Collections can be private,
    friends-only, or public, and can optionally allow collaborators to add games.
    """

    name = models.CharField(_("name"), max_length=255, help_text="The name of the collection.")
    description = models.TextField(
        _("description"),
        blank=True,
        max_length=1000,
        help_text="An optional description of the collection.",
    )
    is_favorite = models.BooleanField(
        _("is favorite"),
        default=False,
        help_text="Whether the collection is marked as a favorite by its owner.",
    )
    is_moderated = models.BooleanField(
        _("is moderated"),
        default=False,
        help_text="Whether an accepted Report has flagged this collection's name/description for masking.",
    )
    visibility = models.CharField(
        _("visibility"),
        max_length=3,
        choices=CollectionVisibility.choices,
        default=CollectionVisibility.PRIVATE,
        help_text="Visibility level: PUBLIC, FRIENDS (friends only), or PRIVATE.",
    )
    mode = models.CharField(
        _("mode"),
        max_length=1,
        choices=CollectionMode.choices,
        default=CollectionMode.SOLO,
        help_text="Collection mode: SOLO (single owner) or COLLABORATIVE (multiple contributors).",
    )
    type = models.CharField(
        _("type"),
        max_length=3,
        choices=CollectionType.choices,
        default=CollectionType.NORMAL,
        help_text="Collection type: NORMAL, RANK (ordered ranking), or TIER (tier list).",
    )
    created_at = models.DateTimeField(_("creation time"), auto_now_add=True)
    last_modified_at = models.DateTimeField(_("last modified"), auto_now=True)
    slug = models.SlugField(
        _("slug"),
        max_length=512,
        unique=True,
        blank=True,
        help_text="URL-safe identifier auto-generated from the owner username and collection name.",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections",
        verbose_name=_("owner"),
        help_text="The owner of the collection.",
    )
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="collaborated_collections",
        blank=True,
        verbose_name=_("collaborators"),
        help_text="Users allowed to add and reorder items in COLLABORATIVE collections.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the collection model."""

        verbose_name = _("collection")
        verbose_name_plural = _("collections")

    def __str__(self: Self) -> str:
        """String representation of the collection model."""
        return f"{self.user.username} - {self.name}"

    def save(self: Self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Save the collection and generate a slug based on the name."""
        if not self.slug and self.name:
            self.slug = generate_unique_slug(
                Collection,
                f"{self.user.username}-{self.name}",
                exclude_pk=self.pk,
            )
        super().save(*args, **kwargs)


class CollectionItem(BaseModel):
    """A model representing a game within a collection.

    Collection items link games to collections and store additional metadata
    like ranking order, optional tier classification, and justification notes.
    """

    order = models.DecimalField(
        _("order"),
        max_digits=20,
        decimal_places=10,
        null=True,
        db_index=True,
        help_text="Fractional decimal position within the collection. Lower values appear first.",
    )
    tier = models.CharField(
        _("tier"),
        max_length=1,
        choices=Tier.choices,
        blank=True,
        db_index=True,
        help_text="Optional tier classification for TIER-type collections (S, A, B, C, D, or E).",
    )
    description = models.TextField(
        _("description"),
        blank=True,
        max_length=500,
        help_text="Optional notes or justification for this item's position in the collection.",
    )
    is_moderated = models.BooleanField(
        _("is moderated"),
        default=False,
        help_text="Whether an accepted Report has flagged this item's note for masking.",
    )
    created_at = models.DateTimeField(_("creation time"), auto_now_add=True)
    last_modified_at = models.DateTimeField(_("last modified"), auto_now=True)

    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("collection"),
        help_text="The collection this item belongs to.",
    )
    game = models.ForeignKey(
        "games.Game",
        on_delete=models.PROTECT,
        related_name="collection_items",
        verbose_name=_("game"),
        help_text="The game this item represents.",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="collection_items_added",
        verbose_name=_("added by"),
        help_text="The user who added this item. May be null if the adding user was deleted.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the collection item model."""

        verbose_name = _("collection item")
        verbose_name_plural = _("collection items")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("collection", "game"), name="unique_collection_game"),
        ]

    def __str__(self: Self) -> str:
        """String representation of the collection item model."""
        return f"{self.collection.name} - {self.game.title} (#{self.order})"
