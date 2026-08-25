"""Filters for collection related data."""

from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

if TYPE_CHECKING:
    from django.db.models import QuerySet

from game_list.collections.models import (
    Collection,
    CollectionItem,
    CollectionMode,
    CollectionType,
    CollectionVisibility,
    Tier,
)


class CollectionFilterSet(filters.FilterSet):
    """FilterSet for collection model."""

    name = filters.CharFilter(lookup_expr="icontains")
    user = filters.NumberFilter(field_name="user__id")
    visibility = filters.MultipleChoiceFilter(choices=CollectionVisibility.choices)
    mode = filters.MultipleChoiceFilter(choices=CollectionMode.choices)
    type = filters.MultipleChoiceFilter(choices=CollectionType.choices)
    is_favorite = filters.BooleanFilter()
    collaborator = filters.NumberFilter(field_name="collaborators__id")
    member = filters.NumberFilter(
        label=_("Member"),
        method="filter_member",
    )

    def filter_member(
        self,
        queryset: QuerySet[Collection],
        name: str,  # noqa: ARG002
        value: int,
    ) -> QuerySet[Collection]:
        """Filter collections where the given user is the owner or a collaborator.

        Args:
            queryset: The queryset to filter
            name: The field name (unused)
            value: The user ID to check
        """
        return queryset.filter(Q(user__id=value) | Q(collaborators__id=value)).distinct()

    class Meta:
        """Meta class for collection filter set."""

        model = Collection
        fields = (
            "id",
            "name",
            "user",
            "visibility",
            "mode",
            "type",
            "is_favorite",
            "collaborator",
            "member",
        )


class CollectionItemFilterSet(filters.FilterSet):
    """FilterSet for collection item model."""

    collection = filters.NumberFilter(field_name="collection__id")
    game = filters.NumberFilter(field_name="game__id")
    tier = filters.MultipleChoiceFilter(choices=Tier.choices)
    has_tier = filters.BooleanFilter(label=_("Has Tier"), method="filter_has_tier")
    added_by = filters.NumberFilter(field_name="added_by__id")

    def filter_has_tier(
        self,
        queryset: QuerySet[CollectionItem],
        name: str,  # noqa: ARG002
        value: bool,  # noqa: FBT001
    ) -> QuerySet[CollectionItem]:
        """Filter for items with or without a tier.

        Args:
            queryset: The queryset to filter
            name: The field name (unused)
            value: True to get items with a tier, False for items without a tier
        """
        if value is True:
            return queryset.exclude(tier="")
        if value is False:
            return queryset.filter(tier="")
        return queryset

    ordering = filters.OrderingFilter(
        fields=(
            ("order", "order"),
            ("created_at", "created_at"),
            ("tier", "tier"),
        ),
    )

    class Meta:
        """Meta class for collection item filter set."""

        model = CollectionItem
        fields = (
            "id",
            "collection",
            "game",
            "tier",
            "has_tier",
            "added_by",
        )
