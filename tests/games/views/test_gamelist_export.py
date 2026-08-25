"""Test the export action on GameListViewSet."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.games.models import GameList


@pytest.mark.django_db()
def test_export_returns_the_authenticated_users_full_game_list(
    authenticated_api_client: APIClient,
    game_list_fixture: GameList,
) -> None:
    """Exporting returns the authenticated user's game list entries, description included."""
    response = authenticated_api_client.get(reverse("games:game-lists-export"))

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {entry["id"] for entry in response.data}
    assert game_list_fixture.id in returned_ids


@pytest.mark.django_db()
def test_export_unauthenticated_returns_401(api_client: APIClient) -> None:
    """Unauthenticated requests cannot export a game list."""
    response = api_client.get(reverse("games:game-lists-export"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
