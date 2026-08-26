"""Test the random ptp endpoint for GameList."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import GameList, GameListStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_random_ptp_success(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Test the random ptp endpoint returns a game."""
    api_client.force_authenticate(user=user_fixture)

    game_list: GameList = baker.make("games.GameList", user=user_fixture, status=GameListStatus.PLAN_TO_PLAY)

    response = api_client.get(reverse("games:game-lists-random-ptp"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == game_list.id


@pytest.mark.django_db()
def test_random_ptp_unauthenticated(api_client: APIClient) -> None:
    """Test the random ptp endpoint returns 401 for an unauthenticated request."""
    response = api_client.get(reverse("games:game-lists-random-ptp"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_random_ptp_not_found(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Test the random ptp endpoint returns 404 if no ptp game exists."""
    api_client.force_authenticate(user=user_fixture)

    baker.make("games.GameList", user=user_fixture, status=GameListStatus.COMPLETED)

    response = api_client.get(reverse("games:game-lists-random-ptp"))

    assert response.status_code == status.HTTP_404_NOT_FOUND
