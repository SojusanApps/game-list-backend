"""Test the bulk-create endpoint on GameListViewSet."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import Game, GameList, GameListStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_bulk_create_unauthenticated(api_client: APIClient) -> None:
    """Unauthenticated request returns 401."""
    response = api_client.post(reverse("games:game-lists-bulk-create"), [], format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_bulk_create_empty_array_returns_400(api_client: APIClient, user_fixture: UserModel) -> None:
    """Submitting an empty array returns 400."""
    api_client.force_authenticate(user=user_fixture)
    response = api_client.post(reverse("games:game-lists-bulk-create"), [], format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_bulk_create_valid_payload_creates_entries(api_client: APIClient, user_fixture: UserModel) -> None:
    """Valid payload with N entries returns 201 and creates N GameList records."""
    game1: Game = baker.make("games.Game")
    game2: Game = baker.make("games.Game")
    api_client.force_authenticate(user=user_fixture)
    payload = [
        {"game": game1.id, "status": GameListStatus.PLAN_TO_PLAY},
        {"game": game2.id, "status": GameListStatus.COMPLETED},
    ]
    response = api_client.post(reverse("games:game-lists-bulk-create"), payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert GameList.objects.filter(user=user_fixture).count() == 2  # noqa: PLR2004


@pytest.mark.django_db()
def test_bulk_create_user_set_from_request(api_client: APIClient, user_fixture: UserModel) -> None:
    """The user on every created entry is the authenticated user, regardless of payload."""
    other_user: UserModel = baker.make("users.User")
    game: Game = baker.make("games.Game")
    api_client.force_authenticate(user=user_fixture)
    payload = [{"game": game.id, "status": GameListStatus.PLAN_TO_PLAY, "user": other_user.id}]
    response = api_client.post(reverse("games:game-lists-bulk-create"), payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert GameList.objects.get(game=game).user == user_fixture


@pytest.mark.django_db()
def test_bulk_create_invalid_entry_rolls_back_all(api_client: APIClient, user_fixture: UserModel) -> None:
    """If any entry is invalid, 0 records are created (atomic rollback)."""
    game: Game = baker.make("games.Game")
    # Create a duplicate: same game + user already in DB
    baker.make(GameList, game=game, user=user_fixture, status=GameListStatus.COMPLETED)

    game2: Game = baker.make("games.Game")
    api_client.force_authenticate(user=user_fixture)
    payload = [
        {"game": game2.id, "status": GameListStatus.PLAN_TO_PLAY},  # valid
        {"game": game.id, "status": GameListStatus.PLAN_TO_PLAY},  # duplicate — should fail
    ]
    response = api_client.post(reverse("games:game-lists-bulk-create"), payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # Only the pre-existing entry remains — the valid game2 entry was rolled back
    assert GameList.objects.filter(user=user_fixture).count() == 1
