"""Tests for the Title Import endpoint (step 1: match pasted titles to catalogue games)."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import Game, GameList
from game_list.games.views import MAX_MATCHES_PER_IMPORTED_TITLE

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel


TITLE_IMPORT_URL = "games:game-lists-title-import"


def _post_titles(api_client: APIClient, titles: list[str]) -> _MonkeyPatchedResponse:
    return api_client.post(reverse(TITLE_IMPORT_URL), {"titles": titles}, format="json")


@pytest.mark.django_db()
def test_title_import_requires_authentication(api_client: APIClient) -> None:
    """An unauthenticated request is rejected."""
    response = _post_titles(api_client, ["Half-Life"])

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_title_import_matches_title_to_game(api_client: APIClient, user_fixture: UserModel) -> None:
    """A matched title returns the game's id, title and cover_image_id."""
    game = baker.make(Game, title_en="Half-Life", title_pl="Half-Life", cover_image_id="co1xyz")
    api_client.force_authenticate(user=user_fixture)

    response = _post_titles(api_client, ["half life"])

    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["title"] == "half life"
    assert results[0]["matches"] == [
        {"id": game.pk, "title": "Half-Life", "cover_image_id": "co1xyz", "already_in_list": False},
    ]


@pytest.mark.django_db()
def test_title_import_returns_empty_matches_for_unknown_title(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A title with no candidate above the threshold gets an empty matches list."""
    baker.make(Game, title_en="Half-Life", title_pl="Half-Life")
    api_client.force_authenticate(user=user_fixture)

    response = _post_titles(api_client, ["xyzxyzxyz"])

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"] == [{"title": "xyzxyzxyz", "matches": []}]


@pytest.mark.django_db()
def test_title_import_preserves_input_order(api_client: APIClient, user_fixture: UserModel) -> None:
    """Results mirror the input list in order, including unmatched titles in between."""
    baker.make(Game, title_en="Half-Life", title_pl="Half-Life")
    baker.make(Game, title_en="Hades", title_pl="Hades")
    api_client.force_authenticate(user=user_fixture)

    response = _post_titles(api_client, ["hades", "xyzxyzxyz", "half life"])

    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert [r["title"] for r in results] == ["hades", "xyzxyzxyz", "half life"]
    assert [len(r["matches"]) for r in results] == [1, 0, 1]


@pytest.mark.django_db()
def test_title_import_returns_at_most_three_candidates(api_client: APIClient, user_fixture: UserModel) -> None:
    """A title matching many games returns only the three best candidates."""
    for suffix in ("", " II", " III", " IV"):
        baker.make(Game, title_en=f"Hades{suffix}", title_pl=f"Hades{suffix}")
    api_client.force_authenticate(user=user_fixture)

    response = _post_titles(api_client, ["hades"])

    assert response.status_code == status.HTTP_200_OK
    matches = response.json()["results"][0]["matches"]
    assert len(matches) == MAX_MATCHES_PER_IMPORTED_TITLE
    assert matches[0]["title"] == "Hades"


@pytest.mark.django_db()
def test_title_import_ranks_exact_match_first(api_client: APIClient, user_fixture: UserModel) -> None:
    """An exact title match is the first candidate, before partial matches."""
    witcher_3 = baker.make(Game, title_en="The Witcher 3: Wild Hunt", title_pl="Wiedźmin 3: Dziki Gon")
    exact = baker.make(Game, title_en="The Witcher", title_pl="Wiedźmin")
    api_client.force_authenticate(user=user_fixture)

    response = _post_titles(api_client, ["The Witcher"])

    assert response.status_code == status.HTTP_200_OK
    matches = response.json()["results"][0]["matches"]
    assert [match["id"] for match in matches] == [exact.pk, witcher_3.pk]


@pytest.mark.django_db()
def test_title_import_flags_games_already_in_list(api_client: APIClient, user_fixture: UserModel) -> None:
    """A candidate already on the user's game list is flagged, not hidden."""
    owned = baker.make(Game, title_en="Hades", title_pl="Hades")
    baker.make(GameList, game=owned, user=user_fixture)
    api_client.force_authenticate(user=user_fixture)

    response = _post_titles(api_client, ["hades"])

    assert response.status_code == status.HTTP_200_OK
    matches = response.json()["results"][0]["matches"]
    assert matches == [
        {"id": owned.pk, "title": "Hades", "cover_image_id": owned.cover_image_id, "already_in_list": True},
    ]


@pytest.mark.django_db()
def test_title_import_answers_duplicated_titles_twice(api_client: APIClient, user_fixture: UserModel) -> None:
    """Duplicated input titles are not deduplicated; each gets its own result row."""
    baker.make(Game, title_en="Hades", title_pl="Hades")
    api_client.force_authenticate(user=user_fixture)

    response = _post_titles(api_client, ["hades", "hades"])

    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert [result["title"] for result in results] == ["hades", "hades"]
    assert results[0] == results[1]


@pytest.mark.django_db()
@pytest.mark.parametrize(
    "titles",
    [
        [],
        [""],
        ["   Hades   " * 30],
        ["Hades"] * 11,
    ],
    ids=["empty-list", "blank-title", "title-too-long", "too-many-titles"],
)
def test_title_import_rejects_invalid_input(
    api_client: APIClient,
    user_fixture: UserModel,
    titles: list[str],
) -> None:
    """Empty lists, blank or overlong titles, and more than 100 titles are rejected."""
    api_client.force_authenticate(user=user_fixture)

    response = _post_titles(api_client, titles)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
