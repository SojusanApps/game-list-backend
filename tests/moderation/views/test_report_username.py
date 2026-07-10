"""Test reporting and moderating a User's username."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_report_against_username_snapshots_value_and_no_content_fk(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Reporting another user's username creates a pending Report snapshotting the live username."""
    payload = {
        "target_type": ReportTargetType.USERNAME,
        "reported_user": other_user_fixture.id,
        "reason": "This username is offensive.",
    }

    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    report = Report.objects.get(id=response.data["id"])
    assert report.reported_by == user_fixture
    assert report.reported_user == other_user_fixture
    assert report.reported_value == other_user_fixture.username
    assert report.target_review is None
    assert report.status == Report.Status.PENDING


@pytest.mark.django_db()
def test_create_rejects_self_report_of_own_username(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A user cannot report their own username."""
    payload = {
        "target_type": ReportTargetType.USERNAME,
        "reported_user": user_fixture.id,
        "reason": "I regret my own username.",
    }
    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_rejects_second_pending_username_report_from_same_reporter_same_user(
    authenticated_api_client: APIClient,
    other_user_fixture: UserModel,
) -> None:
    """A second pending username report from the same reporter against the same user is rejected."""
    payload = {
        "target_type": ReportTargetType.USERNAME,
        "reported_user": other_user_fixture.id,
        "reason": "First report.",
    }
    first_response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")
    assert first_response.status_code == status.HTTP_201_CREATED

    second_response = authenticated_api_client.post(
        reverse("moderation:reports-list"),
        {**payload, "reason": "Second report."},
        format="json",
    )

    assert second_response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_allows_independent_avatar_and_username_reports_against_same_user(
    api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """An AVATAR report and a USERNAME report against the same user don't collide with each other."""
    api_client.force_authenticate(user=user_fixture)
    avatar_response = api_client.post(
        reverse("moderation:reports-list"),
        {"target_type": ReportTargetType.AVATAR, "reported_user": other_user_fixture.id, "reason": "Bad avatar."},
        format="json",
    )
    assert avatar_response.status_code == status.HTTP_201_CREATED

    api_client.force_authenticate(user=admin_user_fixture)
    username_response = api_client.post(
        reverse("moderation:reports-list"),
        {"target_type": ReportTargetType.USERNAME, "reported_user": other_user_fixture.id, "reason": "Bad name."},
        format="json",
    )
    assert username_response.status_code == status.HTTP_201_CREATED
