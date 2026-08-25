"""Tasks for the notifications app."""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from game_list.games.models import GameFollow
from game_list.notifications.constants import (
    NotificationCategory,
    NotificationDescription,
    NotificationLevel,
    NotificationVerb,
)
from game_list.notifications.models import Notification
from game_list.notifications.utils import notify_send

logger = logging.getLogger(__name__)


@shared_task
def notify_game_releases() -> None:
    """Send notifications for games releasing today and in 7 days."""
    today = timezone.now().date()
    next_week = today + timedelta(days=7)

    # Releasing today
    follows_today = GameFollow.objects.filter(game__release_date=today).select_related("game", "user")
    for follow in follows_today:
        verb = NotificationVerb.GAME_PREMIERES_TODAY
        if not Notification.objects.filter(
            recipient=follow.user,
            verb=verb,
            category=NotificationCategory.RELEASE,
            data__game_id=follow.game_id,
        ).exists():
            notify_send(
                sender=follow.game,
                recipient=follow.user,
                verb=verb,
                level=NotificationLevel.INFO,
                category=NotificationCategory.RELEASE,
                description=NotificationDescription.GAME_PREMIERES_TODAY,
                data={
                    "game_id": follow.game_id,
                    "game_slug": follow.game.slug,
                    "game_title_en": follow.game.title_en or "",
                    "game_title_pl": follow.game.title_pl or follow.game.title_en or "",
                },
            )

    # Releasing in 7 days
    follows_next_week = GameFollow.objects.filter(game__release_date=next_week).select_related("game", "user")
    for follow in follows_next_week:
        verb = NotificationVerb.GAME_PREMIERES_IN_A_WEEK
        if not Notification.objects.filter(
            recipient=follow.user,
            verb=verb,
            category=NotificationCategory.RELEASE,
            data__game_id=follow.game_id,
        ).exists():
            notify_send(
                sender=follow.game,
                recipient=follow.user,
                verb=verb,
                level=NotificationLevel.INFO,
                category=NotificationCategory.RELEASE,
                description=NotificationDescription.GAME_PREMIERES_IN_A_WEEK,
                data={
                    "game_id": follow.game_id,
                    "game_slug": follow.game.slug,
                    "game_title_en": follow.game.title_en or "",
                    "game_title_pl": follow.game.title_pl or follow.game.title_en or "",
                },
            )


@shared_task
def cleanup_old_notifications() -> None:
    """
    Delete old notifications.

    Read notifications older than 14 days and unread notifications older than 30 days.
    """
    now = timezone.now()
    read_cutoff = now - timedelta(days=14)
    unread_cutoff = now - timedelta(days=30)

    # Delete read notifications older than 14 days
    read_deleted_count, _ = Notification.objects.filter(unread=False, timestamp__lt=read_cutoff).delete()

    # Delete unread notifications older than 30 days
    unread_deleted_count, _ = Notification.objects.filter(unread=True, timestamp__lt=unread_cutoff).delete()

    logger.info(
        "Notification cleanup task finished. Deleted %d read and %d unread notifications.",
        read_deleted_count,
        unread_deleted_count,
    )
