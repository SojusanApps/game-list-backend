"""User related filters."""

from django_filters import rest_framework as filters

from game_list.users.models import Gender, User


class UserFilterSet(filters.FilterSet):
    """FilterSet for user model."""

    gender = filters.MultipleChoiceFilter(choices=Gender.choices)
    username = filters.CharFilter(lookup_expr="icontains")
    is_active = filters.BooleanFilter()

    class Meta:
        """Meta class for user filter set."""

        model = User
        fields = (
            "id",
            "gender",
            "username",
            "is_active",
        )
