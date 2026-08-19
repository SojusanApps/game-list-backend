"""This module contains all custom exceptions."""

from typing import Self

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException


class SojusanGameListError(Exception):
    """Base class for all exceptions in the application."""


class ConflictException(APIException):
    """Exception class for http conflict status."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = _("There is a conflict with the current state of the target resource.")
    default_code = "conflict"


class SerializerValidationDetailError(SojusanGameListError):
    """Exception class for wrong type of the validation details."""

    def __init__(self: Self) -> None:
        """Initialize the validation details."""
        super().__init__("Validation error detail returns wrong structure.")
