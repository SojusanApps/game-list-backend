"""Wiring check: TranslationSuggestionSerializer.proposed_value goes through the shared masking helper."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import TranslationSuggestion, TranslationSuggestionField
from game_list.moderation.masking import MODERATION_PLACEHOLDER_TEXT

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_moderated_suggestion_shows_placeholder_to_stranger_and_real_text_to_submitter(
    api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A suggestion flagged is_moderated shows the placeholder to a stranger but the real text to its submitter."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="a bad proposed translation",
        is_moderated=True,
    )

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(
        reverse("games:translation-suggestions-detail", kwargs={"pk": suggestion.id}),
    )
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["proposed_value"] == MODERATION_PLACEHOLDER_TEXT

    api_client.force_authenticate(user=user_fixture)
    submitter_response = api_client.get(
        reverse("games:translation-suggestions-detail", kwargs={"pk": suggestion.id}),
    )
    assert submitter_response.status_code == status.HTTP_200_OK
    assert submitter_response.data["proposed_value"] == suggestion.proposed_value


@pytest.mark.django_db()
def test_banned_users_unreported_suggestion_is_masked_for_stranger_but_not_submitter(
    api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A never-individually-reported suggestion from a banned user is masked for strangers, visible to submitter."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="a proposed translation",
    )
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])

    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")
    api_client.force_authenticate(user=stranger)
    stranger_response = api_client.get(
        reverse("games:translation-suggestions-detail", kwargs={"pk": suggestion.id}),
    )
    assert stranger_response.status_code == status.HTTP_200_OK
    assert stranger_response.data["proposed_value"] == MODERATION_PLACEHOLDER_TEXT

    api_client.force_authenticate(user=user_fixture)
    submitter_response = api_client.get(
        reverse("games:translation-suggestions-detail", kwargs={"pk": suggestion.id}),
    )
    assert submitter_response.status_code == status.HTTP_200_OK
    assert submitter_response.data["proposed_value"] == suggestion.proposed_value


@pytest.mark.django_db()
def test_banned_user_can_still_submit_and_have_accepted_a_new_suggestion(
    api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A banned user can still submit a suggestion and have it accepted - no write-time restriction."""
    user_fixture.is_banned = True
    user_fixture.save(update_fields=["is_banned"])
    api_client.force_authenticate(user=user_fixture)

    create_response = api_client.post(
        reverse("games:translation-suggestions-list"),
        {"game": game_fixture.id, "field": TranslationSuggestionField.SUMMARY, "proposed_value": "new text"},
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    api_client.force_authenticate(user=admin_user_fixture)
    accept_response = api_client.post(
        reverse("games:translation-suggestions-accept", kwargs={"pk": create_response.data["id"]}),
    )
    assert accept_response.status_code == status.HTTP_200_OK
