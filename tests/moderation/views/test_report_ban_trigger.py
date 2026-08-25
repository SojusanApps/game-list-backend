"""Test that a user's 3rd accepted report automatically bans them."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework.reverse import reverse

from game_list.games.models import GameReview
from game_list.notifications.constants import NotificationCategory, NotificationVerb
from game_list.notifications.models import Notification

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from game_list.moderation.models import Report
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_third_accepted_report_bans_user_and_notification_reflects_ban(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    make_review_report: Callable[..., Report],
) -> None:
    """The 3rd accepted report against a user sets is_banned and sends the ACCOUNT_BANNED notification."""
    reviews: list[GameReview] = [
        GameReview.objects.create(
            review=f"review {i}",
            recommendation=GameReview.Recommendation.UNDECIDED,
            game=baker.make("games.Game"),
            user=other_user_fixture,
        )
        for i in range(3)
    ]
    reports = [make_review_report(admin_user_fixture, review) for review in reviews]

    for report in reports[:2]:
        admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))
    other_user_fixture.refresh_from_db()
    assert other_user_fixture.is_banned is False

    admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": reports[2].id}))

    other_user_fixture.refresh_from_db()
    assert other_user_fixture.is_banned is True
    notification = Notification.objects.get(
        recipient=other_user_fixture,
        category=NotificationCategory.MODERATION,
        verb=NotificationVerb.ACCOUNT_BANNED,
    )
    assert notification.actor == admin_user_fixture
