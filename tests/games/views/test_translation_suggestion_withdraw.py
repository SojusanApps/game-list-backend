"""Test the withdraw action on TranslationSuggestionViewSet."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import TranslationSuggestion, TranslationSuggestionField, TranslationSuggestionStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.fixture
def other_user_fixture() -> UserModel:
    """Create another user, unrelated to the suggestion's submitter."""
    return baker.make(User, username="other_user")


@pytest.mark.django_db()
def test_withdraw_by_submitter_transitions_pending_to_withdrawn(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """The original submitter can withdraw their own pending suggestion."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy opis.",
    )

    response = authenticated_api_client.post(
        reverse("games:translation-suggestions-withdraw", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.WITHDRAWN


@pytest.mark.django_db()
def test_withdraw_by_another_regular_user_is_forbidden(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A user other than the submitter cannot withdraw the suggestion."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy opis.",
    )
    api_client.force_authenticate(user=other_user_fixture)

    response = api_client.post(reverse("games:translation-suggestions-withdraw", kwargs={"pk": suggestion.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.PENDING


@pytest.mark.django_db()
def test_after_withdrawal_same_user_can_resubmit_for_same_game_field(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """After withdrawing, the same user can submit a new pending suggestion for the same game+field."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Pierwsza wersja.",
    )
    withdraw_response = authenticated_api_client.post(
        reverse("games:translation-suggestions-withdraw", kwargs={"pk": suggestion.id}),
    )
    assert withdraw_response.status_code == status.HTTP_200_OK

    payload = {
        "game": game_fixture.id,
        "field": TranslationSuggestionField.SUMMARY,
        "proposed_value": "Druga wersja.",
    }
    create_response = authenticated_api_client.post(
        reverse("games:translation-suggestions-list"),
        payload,
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db()
def test_withdraw_of_non_pending_suggestion_is_rejected(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Withdrawing a suggestion that is no longer pending (e.g. already accepted) is rejected."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy opis.",
        status=TranslationSuggestionStatus.ACCEPTED,
    )

    response = authenticated_api_client.post(
        reverse("games:translation-suggestions-withdraw", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.ACCEPTED


@pytest.mark.django_db()
def test_withdraw_by_admin_is_forbidden(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """An admin (is_staff) cannot withdraw a suggestion they did not submit; withdrawal is submitter-only."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy opis.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-withdraw", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.PENDING
