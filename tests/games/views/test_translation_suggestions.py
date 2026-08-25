"""Test the TranslationSuggestionViewSet: submitting and listing translation suggestions."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import TranslationSuggestion, TranslationSuggestionField, TranslationSuggestionStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_snapshots_current_value_and_forces_pending_status(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Submitting a suggestion snapshots the game's live value and is created as pending."""
    payload = {
        "game": game_fixture.id,
        "field": TranslationSuggestionField.SUMMARY,
        "proposed_value": "Nowy polski opis gry.",
    }
    response = authenticated_api_client.post(reverse("games:translation-suggestions-list"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    suggestion = TranslationSuggestion.objects.get(id=response.data["id"])
    assert suggestion.submitted_by == user_fixture
    assert suggestion.current_value == (game_fixture.summary_pl or "")
    assert suggestion.proposed_value == "Nowy polski opis gry."
    assert suggestion.status == TranslationSuggestion.Status.PENDING


@pytest.mark.django_db()
def test_retrieve_includes_nested_game_and_submitted_by_details(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Retrieving a suggestion nests the game (id/title/slug/cover_image_id) and submitter (id/username/slug)."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Nowy opis.",
    )

    response = authenticated_api_client.get(
        reverse("games:translation-suggestions-detail", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["game"] == {
        "id": game_fixture.id,
        "title": game_fixture.title,
        "slug": game_fixture.slug,
        "cover_image_id": game_fixture.cover_image_id,
    }
    assert response.data["submitted_by"]["id"] == user_fixture.id
    assert response.data["submitted_by"]["username"] == user_fixture.username
    assert response.data["submitted_by"]["slug"] == user_fixture.slug
    assert response.data["reviewed_by"] is None


@pytest.mark.django_db()
def test_create_rejects_proposed_value_exceeding_title_max_length(
    authenticated_api_client: APIClient,
    game_fixture: Game,
) -> None:
    """A proposed title longer than Game.title's max_length (255) is rejected."""
    payload = {
        "game": game_fixture.id,
        "field": TranslationSuggestionField.TITLE,
        "proposed_value": "a" * 256,
    }
    response = authenticated_api_client.post(reverse("games:translation-suggestions-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_rejects_second_pending_suggestion_from_same_user_same_game_field(
    authenticated_api_client: APIClient,
    game_fixture: Game,
) -> None:
    """A second pending suggestion from the same user for the same game+field is rejected."""
    payload = {
        "game": game_fixture.id,
        "field": TranslationSuggestionField.SUMMARY,
        "proposed_value": "Pierwsza sugestia.",
    }
    first_response = authenticated_api_client.post(
        reverse("games:translation-suggestions-list"),
        payload,
        format="json",
    )
    assert first_response.status_code == status.HTTP_201_CREATED

    second_payload = {**payload, "proposed_value": "Druga sugestia."}
    second_response = authenticated_api_client.post(
        reverse("games:translation-suggestions-list"),
        second_payload,
        format="json",
    )

    assert second_response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_allows_competing_suggestion_from_different_user_same_game_field(
    api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A different user may submit their own pending suggestion for the same game+field."""
    payload = {
        "game": game_fixture.id,
        "field": TranslationSuggestionField.SUMMARY,
        "proposed_value": "Sugestia pierwszego uzytkownika.",
    }
    api_client.force_authenticate(user=user_fixture)
    first_response = api_client.post(reverse("games:translation-suggestions-list"), payload, format="json")
    assert first_response.status_code == status.HTTP_201_CREATED

    api_client.force_authenticate(user=admin_user_fixture)
    second_payload = {**payload, "proposed_value": "Sugestia drugiego uzytkownika."}
    second_response = api_client.post(reverse("games:translation-suggestions-list"), second_payload, format="json")

    assert second_response.status_code == status.HTTP_201_CREATED
    assert (
        TranslationSuggestion.objects.filter(
            game=game_fixture,
            field=TranslationSuggestionField.SUMMARY,
            status=TranslationSuggestion.Status.PENDING,
        ).count()
        == 2  # noqa: PLR2004
    )


@pytest.mark.django_db()
def test_list_shows_suggestions_from_other_users_to_any_authenticated_user(
    authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A suggestion submitted by another user is visible in the list to any authenticated user."""
    other_users_suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.TITLE,
        submitted_by=admin_user_fixture,
        current_value=game_fixture.title_pl or "",
        proposed_value="Wiedzmin 3",
    )

    response = authenticated_api_client.get(reverse("games:translation-suggestions-list"))

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {entry["id"] for entry in response.data["results"]}
    assert other_users_suggestion.id in returned_ids


@pytest.mark.django_db()
def test_list_filters_by_game_field_status_and_submitted_by(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """The list endpoint can be filtered by game, field, status, and submitted_by."""
    other_game: Game = baker.make("games.Game")
    target = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.TITLE,
        submitted_by=user_fixture,
        current_value=game_fixture.title_pl or "",
        proposed_value="Wiedzmin 3",
        status=TranslationSuggestionStatus.ACCEPTED,
    )
    TranslationSuggestion.objects.create(
        game=other_game,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=admin_user_fixture,
        current_value=other_game.summary_pl or "",
        proposed_value="Inny opis",
        status=TranslationSuggestionStatus.PENDING,
    )

    response = authenticated_api_client.get(
        reverse("games:translation-suggestions-list"),
        {
            "game": str(game_fixture.id),
            "field": str(TranslationSuggestionField.TITLE),
            "status": str(TranslationSuggestionStatus.ACCEPTED),
            "submitted_by": str(user_fixture.id),
        },
    )

    assert response.status_code == status.HTTP_200_OK
    returned_ids = [entry["id"] for entry in response.data["results"]]
    assert returned_ids == [target.id]


@pytest.mark.django_db()
def test_create_unauthenticated_returns_401(api_client: APIClient, game_fixture: Game) -> None:
    """Unauthenticated requests cannot submit a suggestion."""
    payload = {
        "game": game_fixture.id,
        "field": TranslationSuggestionField.SUMMARY,
        "proposed_value": "Nowy polski opis gry.",
    }
    response = api_client.post(reverse("games:translation-suggestions-list"), payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_create_ignores_client_supplied_submitted_by_current_value_and_status(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Client-supplied submitted_by/current_value/status are ignored; server values are used instead."""
    payload = {
        "game": game_fixture.id,
        "field": TranslationSuggestionField.SUMMARY,
        "proposed_value": "Nowy polski opis gry.",
        "submitted_by": admin_user_fixture.id,
        "current_value": "spoofed current value",
        "status": TranslationSuggestion.Status.ACCEPTED,
    }
    response = authenticated_api_client.post(reverse("games:translation-suggestions-list"), payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    suggestion = TranslationSuggestion.objects.get(id=response.data["id"])
    assert suggestion.submitted_by == user_fixture
    assert suggestion.current_value == (game_fixture.summary_pl or "")
    assert suggestion.status == TranslationSuggestion.Status.PENDING
