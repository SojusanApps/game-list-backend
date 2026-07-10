"""Test that ReportSerializer nests reported_by/reported_user/reviewed_by as UserSimpleSerializer."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from my_game_list.games.models import GameReview
    from my_game_list.moderation.models import Report
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_retrieve_nests_reported_by_and_reported_user_as_simple_user(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """reported_by and reported_user serialize as nested UserSimpleSerializer objects, not bare IDs."""
    report = make_review_report(user_fixture, other_user_game_review_fixture)

    response = authenticated_api_client.get(reverse("moderation:reports-detail", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["reported_by"]["id"] == user_fixture.id
    assert response.data["reported_by"]["username"] == user_fixture.username
    assert response.data["reported_user"]["id"] == other_user_fixture.id
    assert response.data["reported_user"]["username"] == other_user_fixture.username
    assert response.data["reviewed_by"] is None


@pytest.mark.django_db()
def test_accept_nests_reviewed_by_as_simple_user(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
    make_review_report: Callable[..., Report],
) -> None:
    """reviewed_by serializes as a nested UserSimpleSerializer object once a report is accepted."""
    report = make_review_report(admin_user_fixture, other_user_game_review_fixture)

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["reviewed_by"]["id"] == admin_user_fixture.id
    assert response.data["reviewed_by"]["username"] == admin_user_fixture.username
