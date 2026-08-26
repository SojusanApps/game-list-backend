"""This module contains the view for api version."""

from typing import TYPE_CHECKING, Any, Self

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import CharField
from rest_framework.views import APIView

from game_list import __version__

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class ApiVersion(APIView):
    """Endpoint for the version of the application."""

    permission_classes = (AllowAny,)

    @extend_schema(
        description=(
            "Return the current semantic version of the running API. "
            "The version string follows MAJOR.MINOR.PATCH format (e.g. '1.2.3') "
            "and is updated on every release. "
            "This endpoint requires no authentication."
        ),
        responses={
            200: inline_serializer(
                name="VersionSerializer",
                fields={
                    "version": CharField(
                        help_text="The semantic version of the API in MAJOR.MINOR.PATCH format.",
                    ),
                },
            ),
        },
    )
    def get(self: Self, *args: Iterable[Any], **kwargs: Mapping[str, Any]) -> Response:  # noqa: ARG002
        """GET method for the version of the application."""
        version = ".".join(map(str, __version__))
        return Response({"version": version})
