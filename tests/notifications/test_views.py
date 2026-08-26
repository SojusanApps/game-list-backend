"""Test views for the notifications app."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.notifications.models import Notification
from game_list.notifications.utils import notify_send

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_list_returns_only_own_notifications(authenticated_api_client: APIClient, user_fixture: UserModel) -> None:
    """Test that the list endpoint only returns notifications belonging to the authenticated user."""
    other_user = baker.make(User)
    own_notification = notify_send(sender=other_user, recipient=user_fixture, verb="verb for me")
    notify_send(sender=user_fixture, recipient=other_user, verb="verb for someone else")

    response = authenticated_api_client.get(reverse("notification-list"))

    assert response.status_code == status.HTTP_200_OK
    returned_ids = [item["id"] for item in response.data["results"]]
    assert returned_ids == [own_notification.id]


@pytest.mark.django_db()
def test_unread_count_returns_only_unread_for_current_user(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Test that unread_count returns the count of unread notifications for the authenticated user only."""
    other_user = baker.make(User)
    notify_send(sender=other_user, recipient=user_fixture, verb="unread one")
    read_notification = notify_send(sender=other_user, recipient=user_fixture, verb="read one")
    read_notification.mark_as_read()
    notify_send(sender=user_fixture, recipient=other_user, verb="not mine")

    response = authenticated_api_client.get(reverse("notification-unread-count"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"unread_count": 1}


@pytest.mark.django_db()
def test_mark_as_read_marks_notification_as_read(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Test that mark_as_read marks a specific notification as read and returns 204."""
    other_user = baker.make(User)
    notification = notify_send(sender=other_user, recipient=user_fixture, verb="verb")
    assert notification.unread is True

    response = authenticated_api_client.post(reverse("notification-mark-as-read", kwargs={"pk": notification.pk}))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    notification.refresh_from_db()
    assert notification.unread is False


@pytest.mark.django_db()
def test_mark_all_as_read_marks_every_unread_notification(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Test that mark_all_as_read marks all of the user's unread notifications as read and returns 204."""
    other_user = baker.make(User)
    notify_send(sender=other_user, recipient=user_fixture, verb="verb one")
    notify_send(sender=other_user, recipient=user_fixture, verb="verb two")

    response = authenticated_api_client.post(reverse("notification-mark-all-as-read"))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Notification.objects.filter(recipient=user_fixture, unread=True).count() == 0


@pytest.mark.django_db()
def test_delete_all_read_removes_only_read_notifications(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Test that delete_all_read permanently deletes read notifications while keeping unread ones."""
    other_user = baker.make(User)
    read_notification = notify_send(sender=other_user, recipient=user_fixture, verb="read verb")
    read_notification.mark_as_read()
    unread_notification = notify_send(sender=other_user, recipient=user_fixture, verb="unread verb")

    response = authenticated_api_client.delete(reverse("notification-delete-all-read"))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    remaining_ids = set(Notification.objects.filter(recipient=user_fixture).values_list("pk", flat=True))
    assert remaining_ids == {unread_notification.pk}
    assert not Notification.objects.filter(pk=read_notification.pk).exists()
