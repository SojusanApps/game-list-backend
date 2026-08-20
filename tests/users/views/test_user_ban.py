"""Test UserViewSet.ban: the admin standalone ban, independent of any Report or Warning count."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.notifications.constants import NotificationCategory, NotificationVerb
from my_game_list.notifications.models import Notification

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_ban_sets_provenance_fields_and_notifies(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
) -> None:
    """A direct ban sets is_banned plus banned_by/banned_at/ban_reason, independent of any warning history."""
    response = admin_authenticated_api_client.post(
        reverse("users:users-ban", kwargs={"pk": user_fixture.id}),
        {"reason": "Repeated harassment across multiple reports."},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user_fixture.refresh_from_db()
    assert user_fixture.is_banned is True
    assert user_fixture.banned_by == admin_user_fixture
    assert user_fixture.banned_at is not None
    assert user_fixture.ban_reason == "Repeated harassment across multiple reports."

    notification = Notification.objects.get(
        recipient=user_fixture,
        category=NotificationCategory.MODERATION,
        verb=NotificationVerb.ACCOUNT_BANNED,
    )
    assert notification.actor == admin_user_fixture


@pytest.mark.django_db()
def test_ban_requires_a_reason(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Banning without a reason is rejected."""
    response = admin_authenticated_api_client.post(
        reverse("users:users-ban", kwargs={"pk": user_fixture.id}),
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    user_fixture.refresh_from_db()
    assert user_fixture.is_banned is False


@pytest.mark.django_db()
def test_ban_of_already_banned_user_is_rejected(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Banning a user who is already banned is rejected: nothing to do."""
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])

    response = admin_authenticated_api_client.post(
        reverse("users:users-ban", kwargs={"pk": user_fixture.id}),
        {"reason": "Already banned, trying again."},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_ban_of_staff_user_is_rejected(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Banning a staff/admin user through this action is refused."""
    other_staff_user: UserModel = user_fixture.__class__.objects.create(
        username="other_staff",
        email="other_staff@email.com",
        is_staff=True,
    )

    response = admin_authenticated_api_client.post(
        reverse("users:users-ban", kwargs={"pk": other_staff_user.id}),
        {"reason": "Trying to ban another admin."},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    other_staff_user.refresh_from_db()
    assert other_staff_user.is_banned is False


@pytest.mark.django_db()
def test_ban_by_non_staff_is_forbidden(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A non-staff user cannot ban anyone, including themselves."""
    response = authenticated_api_client.post(
        reverse("users:users-ban", kwargs={"pk": user_fixture.id}),
        {"reason": "Trying to ban myself."},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
