"""This module contains the base class for all lookup serializers."""

from typing import Any

from rest_framework import serializers


class BaseLookupSerializer(serializers.ModelSerializer[Any]):
    """A base serializer for lookup models."""

    class Meta:
        """Meta data for lookup models."""

        fields: tuple[str, ...] = ("id", "name")
