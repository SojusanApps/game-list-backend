"""Test reporting and moderating a User's avatar."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_report_against_avatar_has_blank_value_and_no_content_fk(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Reporting another user's avatar creates a pending Report with a blank snapshot and no content FK."""
    payload = {
        "target_type": ReportTargetType.AVATAR,
        "reported_user": other_user_fixture.id,
        "reason": "This avatar contains illegal content.",
    }

    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    report = Report.objects.get(id=response.data["id"])
    assert report.reported_by == user_fixture
    assert report.reported_user == other_user_fixture
    assert report.reported_value == ""
    assert report.target_review is None
    assert report.target_translation_suggestion is None
    assert report.target_game_list is None
    assert report.target_collection is None
    assert report.target_collection_item is None
    assert report.status == Report.StatusChoices.PENDING


@pytest.mark.django_db()
def test_create_rejects_self_report_of_own_avatar(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A user cannot report their own avatar."""
    payload = {
        "target_type": ReportTargetType.AVATAR,
        "reported_user": user_fixture.id,
        "reason": "I regret my own avatar.",
    }
    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_rejects_second_pending_avatar_report_from_same_reporter_same_user(
    authenticated_api_client: APIClient,
    other_user_fixture: UserModel,
) -> None:
    """A second pending avatar report from the same reporter against the same user is rejected."""
    payload = {
        "target_type": ReportTargetType.AVATAR,
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
