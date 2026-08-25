"""Test notifications functionality."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from game_list.notifications.constants import NotificationCategory
from game_list.notifications.models import Notification
from game_list.notifications.utils import notify_send

User = get_user_model()


@pytest.mark.django_db()
def test_notify_send() -> None:
    """Test sending a notification."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="sent you a friend request")

    assert Notification.objects.count() == 1
    assert notification.recipient == user2
    assert notification.actor == user1
    assert notification.verb == "sent you a friend request"
    assert notification.category == NotificationCategory.SYSTEM
    assert notification.unread is True


@pytest.mark.django_db()
def test_mark_as_read() -> None:
    """Test marking a notification as read."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb")
    assert notification.unread is True

    notification.mark_as_read()
    assert notification.unread is False


@pytest.mark.django_db()
def test_filter_notification() -> None:
    """Test filtering notifications by category."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notify_send(sender=user1, recipient=user2, verb="system info", category=NotificationCategory.SYSTEM)
    notify_send(sender=user1, recipient=user2, verb="friend request", category=NotificationCategory.FRIENDSHIP)

    friendship_notifications = Notification.objects.filter(category=NotificationCategory.FRIENDSHIP)
    friendship_notification = friendship_notifications.first()
    assert friendship_notification is not None
    assert friendship_notification.verb == "friend request"

    system_notifications = Notification.objects.filter(category=NotificationCategory.SYSTEM)
    system_notification = system_notifications.first()
    assert system_notification is not None
    assert system_notification.verb == "system info"


@pytest.mark.django_db()
def test_notify_send_rejects_anonymous_recipient() -> None:
    """Test that sending a notification to an unauthenticated recipient raises a ValueError."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106

    with pytest.raises(ValueError, match=r"Recipient must be authenticated\."):
        notify_send(sender=user1, recipient=AnonymousUser(), verb="verb")

    assert Notification.objects.count() == 0


@pytest.mark.django_db()
def test_queryset_unread() -> None:
    """Test that the unread queryset method returns only unread notifications."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    read_notification = notify_send(sender=user1, recipient=user2, verb="read verb")
    read_notification.mark_as_read()
    unread_notification = notify_send(sender=user1, recipient=user2, verb="unread verb")

    unread_notifications = Notification.objects.unread()

    assert list(unread_notifications) == [unread_notification]


@pytest.mark.django_db()
def test_queryset_mark_all_as_read() -> None:
    """Test that mark_all_as_read marks every notification in the queryset as read."""
    expected_updated_count = 2
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notify_send(sender=user1, recipient=user2, verb="verb one")
    notify_send(sender=user1, recipient=user2, verb="verb two")

    updated_count = Notification.objects.unread().mark_all_as_read()

    assert updated_count == expected_updated_count
    assert Notification.objects.unread().count() == 0


@pytest.mark.django_db()
def test_notification_str_representation() -> None:
    """Test the string representation of a notification."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="sent you a friend request")

    assert str(notification) == "user1 sent you a friend request to user2"
