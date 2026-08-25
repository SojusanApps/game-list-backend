"""Test tasks for the notifications app."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker

from my_game_list.games.models import Game, GameFollow
from my_game_list.notifications.constants import NotificationCategory, NotificationDescription
from my_game_list.notifications.models import Notification
from my_game_list.notifications.tasks import cleanup_old_notifications, notify_game_releases
from my_game_list.notifications.utils import notify_send

User = get_user_model()


@pytest.mark.django_db()
def test_notify_game_releases() -> None:
    """Test that notifications are created for games releasing today and in 7 days for users following them."""
    expected_notification_count = 2
    today = timezone.now().date()
    next_week = today + timedelta(days=7)

    # Game releasing today
    game_today = baker.make(Game, title="Game Today", release_date=today)
    user1 = baker.make(User)
    baker.make(GameFollow, game=game_today, user=user1)

    # Game releasing in 7 days
    game_next_week = baker.make(Game, title="Game Next Week", release_date=next_week)
    user2 = baker.make(User)
    baker.make(GameFollow, game=game_next_week, user=user2)

    # Game releasing in 14 days (should not send)
    game_future = baker.make(Game, title="Game Future", release_date=today + timedelta(days=14))
    user3 = baker.make(User)
    baker.make(GameFollow, game=game_future, user=user3)

    assert Notification.objects.count() == 0

    notify_game_releases()

    assert Notification.objects.count() == expected_notification_count

    notification_today = Notification.objects.get(recipient=user1)
    assert notification_today.verb == "premieres today!"
    assert notification_today.actor == game_today
    assert notification_today.category == NotificationCategory.RELEASE
    assert notification_today.data == {
        "game_id": game_today.id,
        "game_slug": game_today.slug,
        "game_title_en": game_today.title_en or "",
        "game_title_pl": game_today.title_pl or game_today.title_en or "",
    }
    assert notification_today.description == NotificationDescription.GAME_PREMIERES_TODAY

    notification_next_week = Notification.objects.get(recipient=user2)
    assert notification_next_week.verb == "premieres in a week!"
    assert notification_next_week.actor == game_next_week
    assert notification_next_week.category == NotificationCategory.RELEASE
    assert notification_next_week.data == {
        "game_id": game_next_week.id,
        "game_slug": game_next_week.slug,
        "game_title_en": game_next_week.title_en or "",
        "game_title_pl": game_next_week.title_pl or game_next_week.title_en or "",
    }
    assert notification_next_week.description == NotificationDescription.GAME_PREMIERES_IN_A_WEEK

    # Test running it again doesn't create duplicate notifications
    notify_game_releases()
    assert Notification.objects.count() == expected_notification_count


@pytest.mark.django_db()
def test_cleanup_old_notifications() -> None:
    """Test that old read and unread notifications are deleted according to their respective cutoffs."""
    remaining_notification_count = 2
    total_notification_count = 4
    now = timezone.now()
    user1 = baker.make(User)
    user2 = baker.make(User)

    old_read = notify_send(sender=user1, recipient=user2, verb="old read")
    old_read.mark_as_read()
    Notification.objects.filter(pk=old_read.pk).update(timestamp=now - timedelta(days=15))

    recent_read = notify_send(sender=user1, recipient=user2, verb="recent read")
    recent_read.mark_as_read()
    Notification.objects.filter(pk=recent_read.pk).update(timestamp=now - timedelta(days=13))

    old_unread = notify_send(sender=user1, recipient=user2, verb="old unread")
    Notification.objects.filter(pk=old_unread.pk).update(timestamp=now - timedelta(days=31))

    recent_unread = notify_send(sender=user1, recipient=user2, verb="recent unread")
    Notification.objects.filter(pk=recent_unread.pk).update(timestamp=now - timedelta(days=29))

    assert Notification.objects.count() == total_notification_count

    cleanup_old_notifications()

    assert Notification.objects.count() == remaining_notification_count
    remaining_ids = set(Notification.objects.values_list("pk", flat=True))
    assert remaining_ids == {recent_read.pk, recent_unread.pk}
