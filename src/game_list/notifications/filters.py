"""Filters for the notifications app."""

from django_filters import rest_framework as filters

from game_list.notifications.constants import NotificationCategory, NotificationLevel
from game_list.notifications.models import Notification


class NotificationFilterSet(filters.FilterSet):
    """FilterSet for the Notification model."""

    category = filters.ChoiceFilter(choices=NotificationCategory.choices)
    level = filters.ChoiceFilter(choices=NotificationLevel.choices)
    unread = filters.BooleanFilter()

    class Meta:
        """Meta data for NotificationFilterSet."""

        model = Notification
        fields = (
            "category",
            "level",
            "unread",
        )
