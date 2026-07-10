"""Test accepting a report against a GameList note."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.moderation.models import ModerationWarning, Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import GameList
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_accept_by_admin_moderates_game_list_note_creates_warning_and_notifies(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_list_fixture: GameList,
) -> None:
    """Accepting a pending report against a GameList note moderates it and issues a warning."""
    report = Report.objects.create(
        target_type=ReportTargetType.GAME_LIST_NOTE,
        target_game_list=other_user_game_list_fixture,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_game_list_fixture.description,
        reason="Harassment.",
    )

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    other_user_game_list_fixture.refresh_from_db()
    assert other_user_game_list_fixture.is_moderated is True

    warning = ModerationWarning.objects.get(report=report)
    assert warning.user == other_user_fixture
