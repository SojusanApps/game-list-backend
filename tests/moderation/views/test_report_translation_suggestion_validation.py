"""Test ReportViewSet.create validation for TranslationSuggestion targets."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.games.models import TranslationSuggestion, TranslationSuggestionField
from my_game_list.moderation.models import ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import Game
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_rejects_self_report_of_own_translation_suggestion(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A user cannot report their own translation suggestion."""
    game: Game = baker.make("games.Game")
    own_suggestion = TranslationSuggestion.objects.create(
        game=game,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game.summary_pl or "",
        proposed_value="my own proposed text",
    )

    payload = {
        "target_type": ReportTargetType.TRANSLATION_SUGGESTION,
        "target_translation_suggestion": own_suggestion.id,
        "reason": "I regret writing this.",
    }
    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_report_against_withdrawn_translation_suggestion_is_allowed(
    authenticated_api_client: APIClient,
    other_user_translation_suggestion_fixture: TranslationSuggestion,
) -> None:
    """A suggestion can be reported regardless of its own pending/accepted/rejected/withdrawn status."""
    other_user_translation_suggestion_fixture.status = TranslationSuggestion.Status.WITHDRAWN
    other_user_translation_suggestion_fixture.save(update_fields=["status"])

    payload = {
        "target_type": ReportTargetType.TRANSLATION_SUGGESTION,
        "target_translation_suggestion": other_user_translation_suggestion_fixture.id,
        "reason": "Still contains harassment even though withdrawn.",
    }
    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
