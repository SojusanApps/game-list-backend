"""Test ReportViewSet list/retrieve visibility scoping."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import GameReview
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_list_returns_only_the_requesters_own_filed_reports(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """A non-staff reporter's list only contains reports they personally filed."""
    own_report = Report.objects.create(
        target_type=ReportTargetType.REVIEW,
        target_review=other_user_game_review_fixture,
        reported_by=user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_game_review_fixture.review,
        reason="Filed by user_fixture.",
    )
    third_user: UserModel = baker.make("users.User", username="third_user", email="third@email.com")
    another_game_review: GameReview = baker.make("games.GameReview", user=other_user_fixture)
    Report.objects.create(
        target_type=ReportTargetType.REVIEW,
        target_review=another_game_review,
        reported_by=third_user,
        reported_user=other_user_fixture,
        reported_value=another_game_review.review,
        reason="Filed by someone else, must not appear.",
    )

    api_client.force_authenticate(user=user_fixture)
    response = api_client.get(reverse("moderation:reports-list"))

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {entry["id"] for entry in response.data["results"]}
    assert returned_ids == {own_report.id}


@pytest.mark.django_db()
def test_list_returns_all_reports_for_staff(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """An is_staff user's list contains every report, regardless of who filed it."""
    report = Report.objects.create(
        target_type=ReportTargetType.REVIEW,
        target_review=other_user_game_review_fixture,
        reported_by=user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_game_review_fixture.review,
        reason="Filed by user_fixture.",
    )

    response = admin_authenticated_api_client.get(reverse("moderation:reports-list"))

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {entry["id"] for entry in response.data["results"]}
    assert report.id in returned_ids


@pytest.mark.django_db()
def test_list_excludes_reports_filed_against_the_requester(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """The reported user (the review's owner) sees no reports filed against their content."""
    Report.objects.create(
        target_type=ReportTargetType.REVIEW,
        target_review=other_user_game_review_fixture,
        reported_by=user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_game_review_fixture.review,
        reason="Should not be visible to the review's owner.",
    )

    api_client.force_authenticate(user=other_user_fixture)
    response = api_client.get(reverse("moderation:reports-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"] == []
