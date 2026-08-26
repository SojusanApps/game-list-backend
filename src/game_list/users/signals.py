"""Signals for the users application."""

from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from game_list.game_list.metrics import Metrics
from game_list.users.models import User


@receiver(post_save, sender=User)
def increment_users_registered_total(
    sender: type[User],  # noqa: ARG001
    created: bool,  # noqa: FBT001
    **kwargs: Any,  # noqa: ARG001, ANN401
) -> None:
    """Increment users_registered_total counter when a new user is created."""
    if created:
        Metrics.users_registered_total.inc()
