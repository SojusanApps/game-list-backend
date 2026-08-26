"""Filters for moderation related data."""

from django_filters import rest_framework as filters

from game_list.moderation.models import Report


class ReportFilterSet(filters.FilterSet):
    """Filter set for the report model."""

    reported_by = filters.NumberFilter(field_name="reported_by__id")
    reported_user = filters.NumberFilter(field_name="reported_user__id")

    class Meta:
        """Meta data for the report filter set."""

        model = Report
        fields = (
            "id",
            "target_type",
            "source",
            "status",
            "reported_by",
            "reported_user",
        )
