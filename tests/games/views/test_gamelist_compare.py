"""Test the compare endpoint for GameList."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.games.models import Game, GameList, GameListStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_compare_unauthenticated(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Test the compare endpoint returns 401 for an unauthenticated request."""
    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_compare_both_users_empty(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Test the compare endpoint returns empty groups when neither user has any games."""
    api_client.force_authenticate(user=user_fixture)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"common": [], "first_user_unique": [], "second_user_unique": []}


@pytest.mark.django_db()
def test_compare_first_user_unique_game(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Test a game only the first user has appears in first_user_unique, other groups stay empty."""
    api_client.force_authenticate(user=user_fixture)
    GameList.objects.create(game=game_fixture, user=user_fixture, status=GameListStatus.PLAYING, score=7)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["common"] == []
    assert data["second_user_unique"] == []
    assert len(data["first_user_unique"]) == 1
    row = data["first_user_unique"][0]
    assert row["game_id"] == game_fixture.id
    assert row["game_slug"] == game_fixture.slug
    assert row["title"] == game_fixture.title
    assert row["first_user_score"] == 7  # noqa: PLR2004
    assert row["first_user_status_code"] == GameListStatus.PLAYING
    assert row["second_user_score"] is None
    assert row["second_user_status"] is None
    assert row["second_user_status_code"] is None


@pytest.mark.django_db()
def test_compare_second_user_unique_game(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Test a game only the second user has appears in second_user_unique, other groups stay empty."""
    api_client.force_authenticate(user=user_fixture)
    GameList.objects.create(game=game_fixture, user=other_user_fixture, status=GameListStatus.COMPLETED, score=9)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["common"] == []
    assert data["first_user_unique"] == []
    assert len(data["second_user_unique"]) == 1
    row = data["second_user_unique"][0]
    assert row["game_id"] == game_fixture.id
    assert row["second_user_score"] == 9  # noqa: PLR2004
    assert row["second_user_status_code"] == GameListStatus.COMPLETED
    assert row["first_user_score"] is None
    assert row["first_user_status"] is None
    assert row["first_user_status_code"] is None


@pytest.mark.django_db()
def test_compare_common_game_same_status(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Test a game both users have (same status) appears once in common with each user's own score/status."""
    api_client.force_authenticate(user=user_fixture)
    GameList.objects.create(game=game_fixture, user=user_fixture, status=GameListStatus.COMPLETED, score=8)
    GameList.objects.create(game=game_fixture, user=other_user_fixture, status=GameListStatus.COMPLETED, score=3)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["first_user_unique"] == []
    assert data["second_user_unique"] == []
    assert len(data["common"]) == 1
    row = data["common"][0]
    assert row["game_id"] == game_fixture.id
    assert row["first_user_score"] == 8  # noqa: PLR2004
    assert row["first_user_status_code"] == GameListStatus.COMPLETED
    assert row["second_user_score"] == 3  # noqa: PLR2004
    assert row["second_user_status_code"] == GameListStatus.COMPLETED


@pytest.mark.django_db()
def test_compare_common_game_different_statuses(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Test a game both users have, with different statuses, is still common and not split."""
    api_client.force_authenticate(user=user_fixture)
    GameList.objects.create(game=game_fixture, user=user_fixture, status=GameListStatus.COMPLETED, score=8)
    GameList.objects.create(game=game_fixture, user=other_user_fixture, status=GameListStatus.PLAN_TO_PLAY)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["first_user_unique"] == []
    assert data["second_user_unique"] == []
    assert len(data["common"]) == 1
    row = data["common"][0]
    assert row["first_user_status_code"] == GameListStatus.COMPLETED
    assert row["second_user_status_code"] == GameListStatus.PLAN_TO_PLAY
    assert row["second_user_score"] is None


@pytest.mark.django_db()
def test_compare_unrated_entry_keeps_null_score(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Test an entry with no score is represented with a null score, not dropped from its group."""
    api_client.force_authenticate(user=user_fixture)
    GameList.objects.create(game=game_fixture, user=user_fixture, status=GameListStatus.DROPPED, score=None)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["first_user_unique"]) == 1
    row = data["first_user_unique"][0]
    assert row["first_user_score"] is None
    assert row["first_user_status_code"] == GameListStatus.DROPPED


@pytest.mark.django_db()
def test_compare_row_includes_game_cover_image(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    game_fixture: Game,
) -> None:
    """Test a comparison row includes the game's cover image ID."""
    api_client.force_authenticate(user=user_fixture)
    GameList.objects.create(game=game_fixture, user=user_fixture, status=GameListStatus.PLAYING)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    row = response.json()["first_user_unique"][0]
    assert row["game_cover_image"] == game_fixture.cover_image_id


@pytest.mark.django_db()
def test_compare_orders_group_alphabetically_by_title(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Test each comparison group is ordered alphabetically by title."""
    api_client.force_authenticate(user=user_fixture)
    zebra = baker.make(Game, title_en="Zebra Quest", title_pl="Zebra Quest")
    apple = baker.make(Game, title_en="Apple Adventure", title_pl="Apple Adventure")
    mango = baker.make(Game, title_en="Mango Mayhem", title_pl="Mango Mayhem")
    for game in (zebra, apple, mango):
        GameList.objects.create(game=game, user=user_fixture, status=GameListStatus.PLAYING)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": other_user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    titles = [row["title"] for row in response.json()["first_user_unique"]]
    assert titles == ["Apple Adventure", "Mango Mayhem", "Zebra Quest"]


@pytest.mark.django_db()
def test_compare_same_user_twice_returns_bad_request(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Test comparing a user against themselves returns 400."""
    api_client.force_authenticate(user=user_fixture)

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": user_fixture.pk},
        ),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_compare_nonexistent_user_returns_not_found(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Test comparing against a user id that doesn't exist returns 404."""
    api_client.force_authenticate(user=user_fixture)
    nonexistent_id = user_fixture.pk + 1000

    response = api_client.get(
        reverse(
            "games:game-lists-compare",
            kwargs={"first_user_id": user_fixture.pk, "second_user_id": nonexistent_id},
        ),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
