"""Test the accept action on TranslationSuggestionViewSet."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.games.models import TranslationSuggestion, TranslationSuggestionField, TranslationSuggestionStatus
from my_game_list.notifications.constants import NotificationCategory
from my_game_list.notifications.models import Notification

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import Game
    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.fixture
def other_user_fixture() -> UserModel:
    """Create another user, unrelated to the suggestion's submitter."""
    return baker.make(User, username="other_user")


@pytest.mark.django_db()
def test_accept_by_admin_applies_proposed_value_and_marks_accepted(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """An admin accepting a suggestion applies its proposed_value to the game and marks it accepted."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy polski opis gry.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-accept", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    game_fixture.refresh_from_db()
    assert game_fixture.summary_pl == "Nowy polski opis gry."
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.ACCEPTED
    assert response.data["reviewed_by"]["id"] == admin_user_fixture.id
    assert response.data["reviewed_by"]["username"] == admin_user_fixture.username
    assert suggestion.reviewed_by == admin_user_fixture
    assert suggestion.reviewed_at is not None


@pytest.mark.django_db()
def test_accept_by_non_staff_submitter_is_forbidden(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A non-staff user, including the suggestion's own submitter, cannot accept it."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy polski opis gry.",
    )

    response = authenticated_api_client.post(
        reverse("games:translation-suggestions-accept", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.PENDING


@pytest.mark.django_db()
def test_accept_of_title_suggestion_recomputes_search_title_via_game_save(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Accepting a title suggestion goes through Game.save(), so search_title picks up the new title_pl."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.TITLE,
        submitted_by=user_fixture,
        current_value=game_fixture.title_pl or "",
        proposed_value="Wiedzmin 3: Dziki Gon",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-accept", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    game_fixture.refresh_from_db()
    assert game_fixture.title_pl == "Wiedzmin 3: Dziki Gon"
    assert "wiedzmin 3 dziki gon" in game_fixture.search_title


@pytest.mark.django_db()
def test_accept_auto_rejects_sibling_pending_suggestions_for_same_game_field(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Accepting a suggestion auto-rejects other pending suggestions for the same game+field."""
    accepted_suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Pierwsza propozycja.",
    )
    sibling_suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=other_user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Druga propozycja.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-accept", kwargs={"pk": accepted_suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    sibling_suggestion.refresh_from_db()
    assert sibling_suggestion.status == TranslationSuggestionStatus.REJECTED


@pytest.mark.django_db()
def test_accept_leaves_suggestions_for_different_field_or_game_untouched(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Accepting a suggestion does not affect pending suggestions for a different field or a different game."""
    other_game: Game = baker.make("games.Game")
    accepted_suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy opis.",
    )
    different_field_suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.TITLE,
        submitted_by=other_user_fixture,
        current_value=game_fixture.title_pl or "",
        proposed_value="Nowy tytul.",
    )
    different_game_suggestion = TranslationSuggestion.objects.create(
        game=other_game,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=other_user_fixture,
        current_value=other_game.summary_pl or "",
        proposed_value="Inny opis.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-accept", kwargs={"pk": accepted_suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    different_field_suggestion.refresh_from_db()
    different_game_suggestion.refresh_from_db()
    assert different_field_suggestion.status == TranslationSuggestionStatus.PENDING
    assert different_game_suggestion.status == TranslationSuggestionStatus.PENDING


@pytest.mark.django_db()
def test_accept_of_non_pending_suggestion_is_rejected(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Accepting a suggestion that is no longer pending (e.g. already withdrawn) is rejected."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy opis.",
        status=TranslationSuggestionStatus.WITHDRAWN,
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-accept", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.WITHDRAWN


@pytest.mark.django_db()
def test_accept_notifies_submitter(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Accepting a suggestion sends a notification to the submitter."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy opis.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-accept", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    notification = Notification.objects.get(
        recipient=user_fixture,
        category=NotificationCategory.TRANSLATION_SUGGESTION,
    )
    assert notification.actor == admin_user_fixture
