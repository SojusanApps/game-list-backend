"""Test reporting and moderating a GameList note (description)."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import GameList
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_report_against_game_list_note_snapshots_value_and_owner(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_game_list_fixture: GameList,
) -> None:
    """Reporting another user's GameList note creates a pending Report with the correct owner and snapshot."""
    payload = {
        "target_type": ReportTargetType.GAME_LIST_NOTE,
        "target_game_list": other_user_game_list_fixture.id,
        "reason": "This note contains harassment.",
    }

    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    report = Report.objects.get(id=response.data["id"])
    assert report.reported_by == user_fixture
    assert report.reported_user == other_user_game_list_fixture.user
    assert report.target_game_list_id == other_user_game_list_fixture.id
    assert report.reported_value == other_user_game_list_fixture.description
    assert report.status == Report.StatusChoices.PENDING
