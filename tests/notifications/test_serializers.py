"""Test serializers for the notifications app."""

import pytest
from django.contrib.auth import get_user_model

from game_list.notifications.constants import NotificationCategory, NotificationDescription, NotificationLevel
from game_list.notifications.models import Notification
from game_list.notifications.serializers import NotificationSerializer
from game_list.notifications.utils import notify_send

User = get_user_model()


@pytest.mark.django_db()
def test_get_actor_returns_user_representation() -> None:
    """Test that get_actor returns a dict with user-specific fields for a user actor."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb")

    actor_data = NotificationSerializer().get_actor(notification)

    assert actor_data is not None
    assert actor_data["id"] == user1.pk
    assert actor_data["str"] == str(user1)
    assert actor_data["type"] == "user"
    assert actor_data["gravatar_url"] == user1.gravatar_url
    assert actor_data["slug"] == user1.slug


@pytest.mark.django_db()
def test_get_actor_returns_none_when_actor_object_is_gone() -> None:
    """Test that get_actor returns None when the actor object no longer exists."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb")
    user1.delete()
    notification.refresh_from_db()

    assert NotificationSerializer().get_actor(notification) is None


@pytest.mark.django_db()
def test_get_target_returns_user_representation() -> None:
    """Test that get_target returns a dict with user-specific fields for a user target."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb", target=user2)

    target_data = NotificationSerializer().get_target(notification)

    assert target_data is not None
    assert target_data["id"] == user2.pk
    assert target_data["str"] == str(user2)
    assert target_data["type"] == "user"
    assert target_data["gravatar_url"] == user2.gravatar_url
    assert target_data["slug"] == user2.slug


@pytest.mark.django_db()
def test_get_target_returns_none_without_target() -> None:
    """Test that get_target returns None when the notification has no target."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb")

    assert NotificationSerializer().get_target(notification) is None


@pytest.mark.django_db()
def test_get_verb_translates_verb() -> None:
    """Test that get_verb returns the translated verb."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="sent you a friend request")

    assert NotificationSerializer().get_verb(notification) == "sent you a friend request"


@pytest.mark.django_db()
def test_get_category_returns_display_label() -> None:
    """Test that get_category returns the human-readable category label."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(
        sender=user1,
        recipient=user2,
        verb="verb",
        category=NotificationCategory.FRIENDSHIP,
    )

    assert NotificationSerializer().get_category(notification) == "Friendship"


@pytest.mark.django_db()
def test_get_level_returns_display_label() -> None:
    """Test that get_level returns the human-readable level label."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb", level=NotificationLevel.WARNING)

    assert NotificationSerializer().get_level(notification) == "Warning"


@pytest.mark.django_db()
def test_get_description_returns_empty_when_blank() -> None:
    """Test that get_description returns the blank description unchanged."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb")

    assert NotificationSerializer().get_description(notification) == ""


@pytest.mark.django_db()
def test_get_description_translates_without_placeholder() -> None:
    """Test that get_description translates a description that has no {game} placeholder."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb", description="A plain description.")

    assert NotificationSerializer().get_description(notification) == "A plain description."


@pytest.mark.django_db()
def test_get_description_formats_game_placeholder() -> None:
    """Test that get_description substitutes the {game} placeholder using the notification data."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(
        sender=user1,
        recipient=user2,
        verb="verb",
        description=NotificationDescription.GAME_PREMIERES_TODAY,
        data={"game_title_en": "Cyberpunk 2077"},
    )

    description = NotificationSerializer().get_description(notification)

    assert description == "Cyberpunk 2077 is out now. Time to play!"


@pytest.mark.django_db()
def test_notification_serializer_full_output() -> None:
    """Test that the full serializer produces all expected fields for a complete notification."""
    user1 = User.objects.create_user(username="user1", password="password", email="user1@email.com")  # noqa: S106
    user2 = User.objects.create_user(username="user2", password="password", email="user2@email.com")  # noqa: S106

    notification = notify_send(sender=user1, recipient=user2, verb="verb", target=user2)

    data = NotificationSerializer(notification).data

    assert data["actor"]["id"] == user1.pk
    assert data["target"]["id"] == user2.pk
    assert data["verb"] == "verb"
    assert isinstance(data["id"], int)
    assert Notification.objects.filter(pk=data["id"]).exists()
