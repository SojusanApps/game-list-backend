"""Test accepting a report against a TranslationSuggestion."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.moderation.models import ModerationWarning, Report, ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import TranslationSuggestion
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_accept_by_admin_moderates_translation_suggestion_creates_warning_and_notifies(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_translation_suggestion_fixture: TranslationSuggestion,
) -> None:
    """Accepting a pending report against a TranslationSuggestion moderates it and issues a warning."""
    report = Report.objects.create(
        target_type=ReportTargetType.TRANSLATION_SUGGESTION,
        target_translation_suggestion=other_user_translation_suggestion_fixture,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_translation_suggestion_fixture.proposed_value,
        reason="Harassment.",
    )

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    other_user_translation_suggestion_fixture.refresh_from_db()
    assert other_user_translation_suggestion_fixture.is_moderated is True

    warning = ModerationWarning.objects.get(report=report)
    assert warning.user == other_user_fixture


@pytest.mark.django_db()
def test_accept_of_report_against_already_accepted_suggestion_does_not_revert_game_field(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_translation_suggestion_fixture: TranslationSuggestion,
) -> None:
    """Accepting a report against an already-accepted suggestion leaves Game.summary_pl untouched."""
    game = other_user_translation_suggestion_fixture.game
    game.summary_pl = other_user_translation_suggestion_fixture.proposed_value
    game.save()
    other_user_translation_suggestion_fixture.status = other_user_translation_suggestion_fixture.Status.ACCEPTED
    other_user_translation_suggestion_fixture.save(update_fields=["status"])

    report = Report.objects.create(
        target_type=ReportTargetType.TRANSLATION_SUGGESTION,
        target_translation_suggestion=other_user_translation_suggestion_fixture,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_translation_suggestion_fixture.proposed_value,
        reason="Harassment.",
    )

    response = admin_authenticated_api_client.post(reverse("moderation:reports-accept", kwargs={"pk": report.id}))

    assert response.status_code == status.HTTP_200_OK
    other_user_translation_suggestion_fixture.refresh_from_db()
    assert other_user_translation_suggestion_fixture.is_moderated is True
    game.refresh_from_db()
    assert game.summary_pl == other_user_translation_suggestion_fixture.proposed_value
