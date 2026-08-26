"""Utility functions for notifications."""

from typing import TYPE_CHECKING, Any

from django.contrib.contenttypes.models import ContentType

from game_list.notifications.constants import NotificationCategory, NotificationLevel
from game_list.notifications.models import Notification

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.db import models

    from game_list.users.models import User


def notify_send(  # noqa: PLR0913, PLR0917, RUF100
    sender: models.Model,
    recipient: User | AnonymousUser,
    verb: str,
    target: models.Model | None = None,
    level: str = NotificationLevel.INFO,
    category: str = NotificationCategory.SYSTEM,
    description: str = "",
    data: dict[str, Any] | None = None,
) -> Notification:
    """Send a notification."""
    if not recipient.is_authenticated:
        msg = "Recipient must be authenticated."
        raise ValueError(msg)

    actor_ct = ContentType.objects.get_for_model(sender)
    target_ct = ContentType.objects.get_for_model(target) if target else None

    return Notification.objects.create(
        recipient=recipient,
        actor_content_type=actor_ct,
        actor_object_id=sender.pk,
        verb=verb,
        target_content_type=target_ct,
        target_object_id=target.pk if target else None,
        level=level,
        category=category,
        description=description,
        data=data,
    )
