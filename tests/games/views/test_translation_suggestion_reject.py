"""Test the reject action on TranslationSuggestionViewSet."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import TranslationSuggestion, TranslationSuggestionField, TranslationSuggestionStatus
from game_list.notifications.constants import NotificationCategory
from game_list.notifications.models import Notification

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import Game
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_reject_by_admin_without_reason_marks_rejected(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """An admin rejecting a suggestion without a reason marks it rejected, blank reason."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Zly opis.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-reject", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.REJECTED
    assert suggestion.reviewed_by == admin_user_fixture
    assert suggestion.reviewed_at is not None
    assert suggestion.rejection_reason == ""


@pytest.mark.django_db()
def test_reject_by_non_staff_submitter_is_forbidden(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A non-staff user, including the suggestion's own submitter, cannot reject it."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Zly opis.",
    )

    response = authenticated_api_client.post(
        reverse("games:translation-suggestions-reject", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.PENDING


@pytest.mark.django_db()
def test_reject_with_reason_stores_it(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """A rejection_reason supplied in the request body is stored on the suggestion."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Zly opis.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-reject", kwargs={"pk": suggestion.id}),
        {"rejection_reason": "Zawiera blad gramatyczny."},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    suggestion.refresh_from_db()
    assert suggestion.rejection_reason == "Zawiera blad gramatyczny."


@pytest.mark.django_db()
def test_reject_of_non_pending_suggestion_is_rejected(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Rejecting a suggestion that is no longer pending (e.g. already accepted) is rejected."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Zly opis.",
        status=TranslationSuggestionStatus.ACCEPTED,
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-reject", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    suggestion.refresh_from_db()
    assert suggestion.status == TranslationSuggestionStatus.ACCEPTED


@pytest.mark.django_db()
def test_reject_never_modifies_the_game_record(
    admin_authenticated_api_client: APIClient,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Rejecting a suggestion leaves the associated Game record's field values untouched."""
    original_summary_pl = game_fixture.summary_pl
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Zly opis, ktory nie powinien trafic do gry.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-reject", kwargs={"pk": suggestion.id}),
    )

    assert response.status_code == status.HTTP_200_OK
    game_fixture.refresh_from_db()
    assert game_fixture.summary_pl == original_summary_pl


@pytest.mark.django_db()
def test_reject_notifies_submitter_including_reason(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Rejecting a suggestion notifies the submitter, including the reason when one was given."""
    suggestion = TranslationSuggestion.objects.create(
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        current_value=game_fixture.summary_pl or "",
        proposed_value="Zly opis.",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:translation-suggestions-reject", kwargs={"pk": suggestion.id}),
        {"rejection_reason": "Zawiera blad gramatyczny."},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    notification = Notification.objects.get(
        recipient=user_fixture,
        category=NotificationCategory.TRANSLATION_SUGGESTION,
    )
    assert notification.actor == admin_user_fixture
    assert "Zawiera blad gramatyczny." in notification.description
