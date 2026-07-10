"""This module contains the user related models."""

import hashlib
from typing import Any, ClassVar, Self

from django.contrib import admin
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.html import format_html
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from my_game_list.my_game_list.models import BaseModel


class Gender(models.TextChoices):
    """The choices for the gender of the user."""

    MALE = "M", _("Male")
    FEMALE = "F", _("Female")


class User(BaseModel, AbstractUser):
    """A model for the application user."""

    email = models.EmailField(
        _("email address"),
        unique=True,
        help_text="The user's email address. Used as the login credential.",
    )
    slug = models.SlugField(
        _("slug"),
        max_length=255,
        unique=True,
        blank=True,
        help_text="URL-safe identifier for the user profile, auto-generated from the username.",
    )
    gender = models.CharField(
        _("gender"),
        max_length=1,
        choices=Gender.choices,
        blank=True,
        help_text="The user's gender. Optional.",
    )
    last_active = models.DateTimeField(
        _("last active"),
        null=True,
        blank=True,
        help_text="Timestamp of the user's most recent activity. Null if never recorded.",
    )
    is_banned = models.BooleanField(
        _("is banned"),
        default=False,
        help_text="Whether this user has accumulated 3 warnings. Distinct from is_active, which gates login.",
    )
    has_moderated_avatar = models.BooleanField(
        _("has moderated avatar"),
        default=False,
        help_text="Whether an accepted avatar Report hides gravatar_url for literally everyone, including self.",
    )
    has_moderated_username = models.BooleanField(
        _("has moderated username"),
        default=False,
        help_text="Whether an accepted username Report masks the username for other viewers.",
    )

    # Delete the unwanted fields from the `AbstractUser`
    # first and last name of the user are sensitive data that will not be used in the application
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["username"]

    def save(self: Self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Save the model and generate a slug based on the username."""
        if not self.slug and self.username:
            self.slug = slugify(self.username)
        super().save(*args, **kwargs)

    def __str__(self: Self) -> str:
        """Return a string representation for this model."""
        return self.username

    @property
    def gravatar_url(self: Self) -> str:
        """Generate the gravatar url for the user."""
        email_hash = hashlib.sha256(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{email_hash}?s=256"

    @property
    @admin.display(description="Gravatar preview")
    def gravatar_tag(self: Self) -> str:
        """Used in admin model to have a image preview."""
        return format_html(
            '<img src={} width="125" height="150">',
            self.gravatar_url,
        )
