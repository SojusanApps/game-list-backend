"""Test that UserDetailSerializer exposes warning_count, restricted to the profile owner and staff."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel

WARNING_COUNT = 2


def _issue_warnings(
    *,
    reported_by: UserModel,
    reported_user: UserModel,
    count: int,
) -> None:
    for i in range(count):
        report = Report.objects.create(
            target_type=ReportTargetType.USERNAME,
            reported_by=reported_by,
            reported_user=reported_user,
            reported_value=f"bad username {i}",
            reason="Offensive.",
            status=Report.Status.ACCEPTED,
        )
        ModerationWarning.objects.create(user=reported_user, report=report, issued_by=reported_by)


@pytest.mark.django_db()
def test_warning_count_visible_to_the_profile_owner(
    api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """The profile owner sees their own real warning_count."""
    _issue_warnings(reported_by=admin_user_fixture, reported_user=other_user_fixture, count=WARNING_COUNT)

    api_client.force_authenticate(user=other_user_fixture)
    response = api_client.get(reverse("users:users-detail", kwargs={"pk": other_user_fixture.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["warning_count"] == WARNING_COUNT


@pytest.mark.django_db()
def test_warning_count_visible_to_staff(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """An is_staff viewer sees the real warning_count for any user."""
    _issue_warnings(reported_by=admin_user_fixture, reported_user=other_user_fixture, count=WARNING_COUNT)

    response = admin_authenticated_api_client.get(reverse("users:users-detail", kwargs={"pk": other_user_fixture.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["warning_count"] == WARNING_COUNT


@pytest.mark.django_db()
def test_warning_count_hidden_from_other_viewers(
    api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """A stranger (not the owner, not staff) does not see the real warning_count."""
    _issue_warnings(reported_by=admin_user_fixture, reported_user=other_user_fixture, count=WARNING_COUNT)

    stranger: UserModel = other_user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    response = api_client.get(reverse("users:users-detail", kwargs={"pk": other_user_fixture.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["warning_count"] is None


@pytest.mark.django_db()
def test_warning_count_is_zero_for_the_owner_of_a_user_with_no_warnings(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """warning_count is 0, not None, for the owner of a user who has never been warned."""
    response = authenticated_api_client.get(reverse("users:users-detail", kwargs={"pk": user_fixture.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["warning_count"] == 0
