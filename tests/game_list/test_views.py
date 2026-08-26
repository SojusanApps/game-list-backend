"""Test the game_list app views."""

from typing import TYPE_CHECKING

from django.urls import reverse
from rest_framework import status

from game_list import __version__

if TYPE_CHECKING:
    from django.test.client import Client


def test_version(client: Client) -> None:
    """Check if api version endpoint works properly."""
    response = client.get(reverse("api-version"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": ".".join(map(str, __version__))}


def test_metrics_endpoint(client: Client) -> None:
    """Check if metrics endpoint works properly."""
    response = client.get(reverse("prometheus-django-metrics"))
    response_text = response.content.decode("utf-8")
    assert response.status_code == status.HTTP_200_OK
    assert len(response_text) > 0
    assert "cpu_usage_percent" in response_text
    assert "memory_usage_percent" in response_text
