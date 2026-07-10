"""Test that the moderation placeholder text respects the request's Accept-Language header."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.games.models import GameReview
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_moderated_review_placeholder_is_english_by_default(
    api_client: APIClient,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """With no Accept-Language header, the placeholder is served in English."""
    other_user_game_review_fixture.is_moderated = True
    other_user_game_review_fixture.save(update_fields=["is_moderated"])
    stranger: UserModel = other_user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")

    api_client.force_authenticate(user=stranger)
    response = api_client.get(
        reverse("games:game-reviews-detail", kwargs={"pk": other_user_game_review_fixture.id}),
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["review"] == "This content has been removed for violating our community guidelines."


@pytest.mark.django_db()
def test_moderated_review_placeholder_respects_polish_accept_language_header(
    api_client: APIClient,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """With Accept-Language: pl, the placeholder is served in Polish."""
    other_user_game_review_fixture.is_moderated = True
    other_user_game_review_fixture.save(update_fields=["is_moderated"])
    stranger: UserModel = other_user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")

    api_client.force_authenticate(user=stranger)
    response = api_client.get(
        reverse("games:game-reviews-detail", kwargs={"pk": other_user_game_review_fixture.id}),
        HTTP_ACCEPT_LANGUAGE="pl",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["review"] == "Ta zawartość została usunięta za naruszenie zasad naszej społeczności."


@pytest.mark.django_db()
def test_moderated_username_placeholder_respects_polish_accept_language_header(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """The username placeholder is also translated per Accept-Language."""
    user_fixture.has_moderated_username = True
    user_fixture.save(update_fields=["has_moderated_username"])
    stranger: UserModel = user_fixture.__class__.objects.create(username="stranger", email="stranger@email.com")

    api_client.force_authenticate(user=stranger)
    response = api_client.get(
        reverse("users:users-detail", kwargs={"pk": user_fixture.id}),
        HTTP_ACCEPT_LANGUAGE="pl",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["username"] == "ZmoderowanyUżytkownik"
