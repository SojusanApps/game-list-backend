"""Middleware relevant to users app."""

from typing import TYPE_CHECKING, Self

from django.core.cache import cache
from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse

# 5 minutes in seconds
LAST_ACTIVITY_COOLDOWN = 300


class UpdateLastActivityMiddleware:
    """Middleware to update the last active timestamp of authenticated users."""

    def __init__(self: Self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize the middleware with the given get_response callable."""
        self.get_response = get_response

    def __call__(self: Self, request: HttpRequest) -> HttpResponse:
        """Process the incoming request and update last active timestamp if needed."""
        response: HttpResponse = self.get_response(request)

        # Ensure user is authenticated
        if request.user.is_authenticated:
            cache_key = f"last_activity_{request.user.id}"

            # Only hit the DB if the cache key doesn't exist
            if not cache.get(cache_key):
                # Update user's last_active field
                request.user.last_active = timezone.now()
                # We use update_fields to only touch `last_active` and avoid
                # saving other fields unnecessarily, or triggering slow signals.
                request.user.save(update_fields=["last_active"])

                # Set a cooldown cache to prevent further DB updates for this user
                cache.set(cache_key, 1, LAST_ACTIVITY_COOLDOWN)

        return response
