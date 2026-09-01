"""FilterSet for friendship related data."""

from django_filters import rest_framework as filters

from game_list.friendships.models import Friendship, FriendshipRequest


class FriendshipFilterSet(filters.FilterSet):
    """FilterSet for friendship model."""

    user = filters.NumberFilter(field_name="user__id")
    friend__username = filters.CharFilter(field_name="friend__username", lookup_expr="icontains")

    class Meta:
        """Meta class for friendship filter set."""

        model = Friendship
        fields = (
            "id",
            "user",
            "friend__username",
        )


class FriendshipRequestFilterSet(filters.FilterSet):
    """FilterSet for friendship request model."""

    sender = filters.NumberFilter(field_name="sender__id")
    receiver = filters.NumberFilter(field_name="receiver__id")

    class Meta:
        """Meta class for friendship request model."""

        model = FriendshipRequest
        fields = (
            "id",
            "sender",
            "receiver",
        )
