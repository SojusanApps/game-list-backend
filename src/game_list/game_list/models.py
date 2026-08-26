"""This module contains the base lookup model for all lookup models in the application."""

from typing import Self

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta


class BaseLookupModel(models.Model):
    """Base class for all lookup models."""

    name = models.CharField(
        _("name"),
        max_length=255,
        unique=True,
        help_text="The display name of this record.",
    )

    class Meta(TypedModelMeta):
        """Meta data for lookup models."""

        abstract = True
        ordering = ("id",)

    def __str__(self: Self) -> str:
        """String representation of lookup models."""
        return self.name


class BaseModel(models.Model):
    """Base class for all models."""

    class Meta(TypedModelMeta):
        """Meta data for all models."""

        abstract = True
        ordering = ("id",)
