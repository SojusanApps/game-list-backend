"""Tests for the store import endpoint (auto-importing a store library by store id)."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import (
    ExternalGame,
    ExternalGameSource,
    Game,
    GameList,
    GameListStatus,
    GameMedia,
    StoreMapping,
)

if TYPE_CHECKING:
    from typing import Any

    from rest_framework.response import _MonkeyPatchedResponse
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel

STORE_IMPORT_URL = "games:game-lists-store-import"


def _entry(
    store_id: str,
    *,
    platform: str = "steam",
    title: str = "Some game",
    wishlisted: bool = False,
) -> dict[str, Any]:
    return {"platform": platform, "store_id": store_id, "title": title, "wishlisted": wishlisted}


def _post(api_client: APIClient, entries: list[dict[str, Any]]) -> _MonkeyPatchedResponse:
    return api_client.post(reverse(STORE_IMPORT_URL), {"entries": entries}, format="json")


def _link_igdb(source_name: str, external_id: str, *games: Game) -> None:
    source = ExternalGameSource.objects.filter(name_en=source_name).first() or baker.make(
        ExternalGameSource,
        name=source_name,
        name_en=source_name,
    )
    external_game = baker.make(ExternalGame, external_game_source=source, external_id=external_id)
    for game in games:
        game.external_games.add(external_game)


def _media(name: str) -> GameMedia:
    media, _ = GameMedia.objects.get_or_create(name_en=name, defaults={"name": name})
    return media


@pytest.mark.django_db()
def test_store_import_requires_authentication(api_client: APIClient) -> None:
    """An unauthenticated request is rejected."""
    assert _post(api_client, [_entry("1")]).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_store_import_rejects_empty_and_unknown_platform(api_client: APIClient, user_fixture: UserModel) -> None:
    """An empty entry list and an unknown platform are 400s."""
    api_client.force_authenticate(user=user_fixture)

    assert _post(api_client, []).status_code == status.HTTP_400_BAD_REQUEST
    assert _post(api_client, [_entry("1", platform="xbox")]).status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_store_import_rejects_too_many_entries(api_client: APIClient, user_fixture: UserModel) -> None:
    """More entries than one request may carry is a 400."""
    api_client.force_authenticate(user=user_fixture)

    response = _post(api_client, [_entry(str(i)) for i in range(5001)])

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_store_import_adds_igdb_match_as_ptp_owned_on_store(api_client: APIClient, user_fixture: UserModel) -> None:
    """An owned game matched through IGDB is added as Plan to Play, unscored, owned on the store."""
    game: Game = baker.make(Game)
    _link_igdb("Steam", "220", game)
    steam = _media("Steam")
    api_client.force_authenticate(user=user_fixture)

    response = _post(api_client, [_entry("220")])

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [(item["platform"], item["store_id"], item["game"]["id"]) for item in body["imported"]] == [
        ("steam", "220", game.pk),
    ]
    assert body["already_added"] == []
    assert body["unmatched"] == []
    game_list = GameList.objects.get(user=user_fixture, game=game)
    assert game_list.status == GameListStatus.PLAN_TO_PLAY
    assert game_list.score is None
    assert list(game_list.owned_on.all()) == [steam]


@pytest.mark.django_db()
def test_store_import_wishlisted_game_has_empty_owned_on(api_client: APIClient, user_fixture: UserModel) -> None:
    """A wishlisted game is added without any owned_on."""
    game: Game = baker.make(Game)
    _link_igdb("GOG", "1207658924", game)
    _media("GOG")
    api_client.force_authenticate(user=user_fixture)

    response = _post(api_client, [_entry("1207658924", platform="gog", wishlisted=True)])

    assert len(response.json()["imported"]) == 1
    assert GameList.objects.get(user=user_fixture, game=game).owned_on.count() == 0


@pytest.mark.django_db()
def test_store_import_appends_store_to_owned_on_of_existing_entry(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """For a game already on the list only the store is appended; nothing else is overwritten."""
    game: Game = baker.make(Game)
    _link_igdb("Steam", "220", game)
    physical, steam = _media("Physical copy"), _media("Steam")
    entry = baker.make(GameList, user=user_fixture, game=game, status=GameListStatus.COMPLETED, score=9)
    entry.owned_on.add(physical)
    api_client.force_authenticate(user=user_fixture)

    body = _post(api_client, [_entry("220")]).json()

    assert body["imported"] == []
    assert [item["game"]["id"] for item in body["already_added"]] == [game.pk]
    entry.refresh_from_db()
    assert (entry.status, entry.score) == (GameListStatus.COMPLETED, 9)
    assert set(entry.owned_on.all()) == {physical, steam}


@pytest.mark.django_db()
def test_store_import_wishlisted_entry_leaves_existing_entry_untouched(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A wishlisted match for a game already on the list changes nothing."""
    game: Game = baker.make(Game)
    _link_igdb("Steam", "220", game)
    _media("Steam")
    entry = baker.make(GameList, user=user_fixture, game=game)
    api_client.force_authenticate(user=user_fixture)

    _post(api_client, [_entry("220", wishlisted=True)])

    assert entry.owned_on.count() == 0


@pytest.mark.django_db()
def test_store_import_missing_game_media_still_imports(api_client: APIClient, user_fixture: UserModel) -> None:
    """When the store has no GameMedia row, the game is still added, with empty owned_on."""
    game: Game = baker.make(Game)
    _link_igdb("Steam", "220", game)
    GameMedia.objects.filter(name_en="Steam").delete()
    api_client.force_authenticate(user=user_fixture)

    assert len(_post(api_client, [_entry("220")]).json()["imported"]) == 1
    assert GameList.objects.get(user=user_fixture, game=game).owned_on.count() == 0


@pytest.mark.django_db()
def test_store_import_unmatched_entries_are_returned(api_client: APIClient, user_fixture: UserModel) -> None:
    """Entries no source knows are returned for the title match step, with nothing created."""
    api_client.force_authenticate(user=user_fixture)

    body = _post(api_client, [_entry("999", title="Mystery", wishlisted=True)]).json()

    assert body["unmatched"] == [_entry("999", title="Mystery", wishlisted=True)]
    assert not GameList.objects.filter(user=user_fixture).exists()


@pytest.mark.django_db()
def test_store_import_same_id_on_another_store_does_not_match(api_client: APIClient, user_fixture: UserModel) -> None:
    """A store id only matches within its own store."""
    game: Game = baker.make(Game)
    _link_igdb("Steam", "220", game)
    api_client.force_authenticate(user=user_fixture)

    body = _post(api_client, [_entry("220", platform="gog")]).json()

    assert len(body["unmatched"]) == 1


@pytest.mark.django_db()
def test_store_import_id_matching_several_games_is_unmatched(api_client: APIClient, user_fixture: UserModel) -> None:
    """An id that points at more than one game is ambiguous, so it is not auto-imported."""
    first, second = baker.make(Game, _quantity=2)
    _link_igdb("Steam", "220", first, second)
    api_client.force_authenticate(user=user_fixture)

    body = _post(api_client, [_entry("220")]).json()

    assert len(body["unmatched"]) == 1
    assert not GameList.objects.filter(user=user_fixture).exists()


@pytest.mark.django_db()
def test_store_import_igdb_wins_over_store_mapping(api_client: APIClient, user_fixture: UserModel) -> None:
    """IGDB is consulted before Store Mappings."""
    igdb_game, mapped_game = baker.make(Game, _quantity=2)
    _link_igdb("Steam", "220", igdb_game)
    baker.make(StoreMapping, platform="steam", store_id="220", game=mapped_game, status=StoreMapping.Status.ACCEPTED)
    api_client.force_authenticate(user=user_fixture)

    body = _post(api_client, [_entry("220")]).json()

    assert [item["game"]["id"] for item in body["imported"]] == [igdb_game.pk]


@pytest.mark.django_db()
def test_store_import_uses_accepted_mapping(api_client: APIClient, user_fixture: UserModel) -> None:
    """An accepted Store Mapping matches for any user."""
    game: Game = baker.make(Game)
    baker.make(StoreMapping, platform="epic", store_id="abc", game=game, status=StoreMapping.Status.ACCEPTED)
    api_client.force_authenticate(user=user_fixture)

    body = _post(api_client, [_entry("abc", platform="epic")]).json()

    assert [item["game"]["id"] for item in body["imported"]] == [game.pk]


@pytest.mark.django_db()
def test_store_import_pending_mapping_applies_only_to_its_submitter(
    api_client: APIClient,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """A pending Store Mapping matches for its submitter and for nobody else."""
    game: Game = baker.make(Game)
    baker.make(
        StoreMapping,
        platform="steam",
        store_id="220",
        game=game,
        submitted_by=user_fixture,
        status=StoreMapping.Status.PENDING,
    )

    api_client.force_authenticate(user=user_fixture)
    assert len(_post(api_client, [_entry("220")]).json()["imported"]) == 1

    api_client.force_authenticate(user=other_user_fixture)
    assert len(_post(api_client, [_entry("220")]).json()["unmatched"]) == 1


@pytest.mark.django_db()
def test_store_import_rejected_mapping_does_not_match(api_client: APIClient, user_fixture: UserModel) -> None:
    """A rejected Store Mapping no longer applies to its submitter."""
    game: Game = baker.make(Game)
    baker.make(
        StoreMapping,
        platform="steam",
        store_id="220",
        game=game,
        submitted_by=user_fixture,
        status=StoreMapping.Status.REJECTED,
    )
    api_client.force_authenticate(user=user_fixture)

    assert len(_post(api_client, [_entry("220")]).json()["unmatched"]) == 1


@pytest.mark.django_db()
def test_store_import_two_store_ids_for_one_game_create_one_entry(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Two store ids that resolve to the same game add it once, owned on both stores."""
    game: Game = baker.make(Game)
    _link_igdb("Steam", "1", game)
    _link_igdb("GOG", "2", game)
    steam, gog = _media("Steam"), _media("GOG")
    api_client.force_authenticate(user=user_fixture)

    body = _post(api_client, [_entry("1"), _entry("2", platform="gog")]).json()

    assert len(body["imported"]) == 2  # noqa: PLR2004
    assert GameList.objects.filter(user=user_fixture, game=game).count() == 1
    assert set(GameList.objects.get(user=user_fixture, game=game).owned_on.all()) == {steam, gog}
