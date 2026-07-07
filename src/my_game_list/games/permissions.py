"""This module contains the custom permission classes for games related data."""

from typing import TYPE_CHECKING, Self

from rest_framework import permissions

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

    from my_game_list.games.models import TranslationSuggestion


class IsSuggestionSubmitter(permissions.BasePermission):
    """Permission to check if the user is the submitter of a translation suggestion."""

    def has_object_permission(
        self: Self,
        request: Request,
        view: APIView,  # noqa: ARG002
        obj: TranslationSuggestion,
    ) -> bool:
        """Check if the user is the submitter of the suggestion."""
        return obj.submitted_by == request.user
