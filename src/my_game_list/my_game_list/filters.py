"""Base filters for lookup models."""

from collections.abc import Collection  # noqa: TC003
from typing import Any, cast

from django import forms as django_forms
from django.db.models import Q, QuerySet
from django_filters import rest_framework as filters


class BilingualModelMultipleChoiceField(django_forms.ModelMultipleChoiceField):  # type: ignore[type-arg]
    """ModelMultipleChoiceField that resolves values by matching en_field or pl_field (iexact)."""

    def __init__(
        self,
        *args: Any,  # noqa: ANN401
        en_field: str = "name_en",
        pl_field: str = "name_pl",
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Initialise with optional en_field and pl_field for bilingual resolution."""
        self.en_field = en_field
        self.pl_field = pl_field
        super().__init__(*args, **kwargs)

    def _check_values(self, value: Collection[Any]) -> QuerySet[Any]:
        qs = cast("QuerySet[Any]", self.queryset)
        matched_pks: list[Any] = []
        for v in value:
            pk = (
                qs.filter(Q(**{f"{self.en_field}__iexact": v}) | Q(**{f"{self.pl_field}__iexact": v}))
                .values_list("pk", flat=True)
                .first()
            )
            if pk is None:
                raise django_forms.ValidationError(
                    self.error_messages["invalid_choice"],
                    code="invalid_choice",
                    params={"value": v},
                )
            matched_pks.append(pk)
        return qs.filter(pk__in=matched_pks)


class BilingualModelMultipleChoiceFilter(filters.ModelMultipleChoiceFilter):
    """ModelMultipleChoiceFilter backed by BilingualModelMultipleChoiceField."""

    field_class = BilingualModelMultipleChoiceField


class BaseLookupFilterSet(filters.FilterSet):
    """Filter set for base lookup models."""

    name = filters.CharFilter(method="filter_name")

    def filter_name(self, queryset: QuerySet[Any], _name: str, value: str) -> QuerySet[Any]:
        """Filter by name in English or Polish."""
        return queryset.filter(Q(name_en__icontains=value) | Q(name_pl__icontains=value))

    class Meta:
        """Meta class for BaseLookupFilterSet."""

        fields: tuple[str, ...] = ("id", "name")
