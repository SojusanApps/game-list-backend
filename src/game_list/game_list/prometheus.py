"""This module contains the Prometheus related logic."""

from typing import TYPE_CHECKING

from django.views.decorators.http import require_http_methods
from django_prometheus.exports import ExportToDjangoView

from game_list.game_list.decorators import (
    calculate_cpu_usage_metric,
    calculate_memory_usage_metric,
)

if TYPE_CHECKING:
    from django.http import HttpResponse
    from rest_framework.request import Request


@calculate_memory_usage_metric
@calculate_cpu_usage_metric
@require_http_methods(["GET"])
def custom_export_to_django_view(request: Request) -> HttpResponse:
    """A wrapper for a function that returns metrics for Prometheus.

    Used to add decorators that configure custom values for metrics set during a request.
    """
    return ExportToDjangoView(request)
