"""Tests for Store Mappings: submitting through bulk-create and the admin review API."""

from typing import TYPE_CHECKING

import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import ExternalGame, ExternalGameSource, Game, GameList, StoreMapping

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel

BULK_CREATE_URL = "games:game-lists-bulk-create"


def _item(
    game: Game,
    *,
    store_id: str = "220",
    platform: str = "steam",
    title: str = "Half-Life 2",
) -> dict[str, object]:
    return {
        "game": game.pk,
        "status": "PTP",
        "store_refs": [{"platform": platform, "store_id": store_id, "store_title": title}],
    }


@pytest.mark.django_db()
def test_bulk_create_records_pending_mapping(api_client: APIClient, user_fixture: UserModel) -> None:
    """Picking a game for a store entry records a pending Store Mapping with the store title snapshot."""
    game: Game = baker.make(Game)
    api_client.force_authenticate(user=user_fixture)

    response = api_client.post(reverse(BULK_CREATE_URL), [_item(game)], format="json")

    assert response.status_code == status.HTTP_201_CREATED
    mapping = StoreMapping.objects.get()
    assert (mapping.platform, mapping.store_id, mapping.store_title) == ("steam", "220", "Half-Life 2")
    assert (mapping.game, mapping.submitted_by, mapping.status) == (game, user_fixture, StoreMapping.Status.PENDING)


@pytest.mark.django_db()
def test_bulk_create_picking_again_replaces_own_pending_mapping(api_client: APIClient, user_fixture: UserModel) -> None:
    """A second pick for the same store id replaces the user's pending mapping instead of adding one."""
    first, second = baker.make(Game, _quantity=2)
    api_client.force_authenticate(user=user_fixture)

    api_client.post(reverse(BULK_CREATE_URL), [_item(first)], format="json")
    api_client.post(reverse(BULK_CREATE_URL), [_item(second)], format="json")

    assert StoreMapping.objects.get().game == second


@pytest.mark.django_db()
def test_bulk_create_without_store_ref_records_nothing(api_client: APIClient, user_fixture: UserModel) -> None:
    """Items without store references (pasted titles) create no mapping."""
    game: Game = baker.make(Game)
    api_client.force_authenticate(user=user_fixture)

    api_client.post(reverse(BULK_CREATE_URL), [{"game": game.pk, "status": "PTP"}], format="json")

    assert not StoreMapping.objects.exists()


@pytest.mark.django_db()
def test_bulk_create_skips_mapping_when_igdb_already_knows_the_game(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """No mapping is recorded when the picked game is already IGDB's match for the store id."""
    game: Game = baker.make(Game)
    source = baker.make(ExternalGameSource, name="Steam", name_en="Steam")
    game.external_games.add(baker.make(ExternalGame, external_game_source=source, external_id="220"))
    api_client.force_authenticate(user=user_fixture)

    api_client.post(reverse(BULK_CREATE_URL), [_item(game)], format="json")

    assert not StoreMapping.objects.exists()


@pytest.mark.django_db()
def test_bulk_create_skips_mapping_when_one_is_already_accepted(api_client: APIClient, user_fixture: UserModel) -> None:
    """No new mapping is recorded for a store id that already has an accepted one."""
    accepted_game, picked = baker.make(Game, _quantity=2)
    baker.make(StoreMapping, platform="steam", store_id="220", game=accepted_game, status=StoreMapping.Status.ACCEPTED)
    api_client.force_authenticate(user=user_fixture)

    api_client.post(reverse(BULK_CREATE_URL), [_item(picked)], format="json")

    assert StoreMapping.objects.count() == 1


@pytest.mark.django_db()
def test_bulk_create_rejects_invalid_store_ref(api_client: APIClient, user_fixture: UserModel) -> None:
    """A malformed store reference is a 400 and nothing is created."""
    game: Game = baker.make(Game)
    api_client.force_authenticate(user=user_fixture)
    item = {"game": game.pk, "status": "PTP", "store_refs": [{"platform": "xbox", "store_id": "1"}]}

    response = api_client.post(reverse(BULK_CREATE_URL), [item], format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not StoreMapping.objects.exists()


@pytest.mark.django_db()
def test_mapping_api_is_admin_only(api_client: APIClient, user_fixture: UserModel) -> None:
    """Regular users and anonymous visitors cannot use the review API."""
    assert api_client.get(reverse("games:store-mappings-list")).status_code == status.HTTP_401_UNAUTHORIZED
    api_client.force_authenticate(user=user_fixture)
    assert api_client.get(reverse("games:store-mappings-list")).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db()
def test_admin_lists_and_filters_mappings(admin_authenticated_api_client: APIClient) -> None:
    """Admins list mappings and can filter them by status."""
    baker.make(StoreMapping, _fill_optional=["game"], status=StoreMapping.Status.PENDING, platform="gog", store_id="1")
    baker.make(StoreMapping, _fill_optional=["game"], status=StoreMapping.Status.REJECTED, platform="gog", store_id="2")

    response = admin_authenticated_api_client.get(reverse("games:store-mappings-list"), {"status": "pending"})

    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert [item["store_id"] for item in results] == ["1"]


@pytest.mark.django_db()
def test_accept_makes_mapping_global_and_rejects_rivals(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Accepting supersedes the accepted mapping and rejects the other pending ones for the store id."""
    game, other_game = baker.make(Game, _quantity=2)
    old = baker.make(StoreMapping, platform="steam", store_id="1", game=other_game, status=StoreMapping.Status.ACCEPTED)
    target = baker.make(
        StoreMapping,
        platform="steam",
        store_id="1",
        game=game,
        submitted_by=user_fixture,
        status="pending",
    )
    rival = baker.make(
        StoreMapping,
        platform="steam",
        store_id="1",
        game=other_game,
        submitted_by=other_user_fixture,
        status="pending",
    )
    unrelated = baker.make(StoreMapping, _fill_optional=["game"], platform="steam", store_id="2", status="pending")

    response = admin_authenticated_api_client.post(reverse("games:store-mappings-accept", kwargs={"pk": target.pk}))

    assert response.status_code == status.HTTP_200_OK
    for mapping in (target, old, rival, unrelated):
        mapping.refresh_from_db()
    assert target.status == StoreMapping.Status.ACCEPTED
    assert target.reviewed_by == admin_user_fixture
    assert old.status == StoreMapping.Status.REJECTED
    assert str(target.pk) in old.rejection_reason
    assert rival.status == StoreMapping.Status.REJECTED
    assert unrelated.status == StoreMapping.Status.PENDING


@pytest.mark.django_db()
def test_accept_only_pending(admin_authenticated_api_client: APIClient) -> None:
    """A mapping that is not pending cannot be accepted."""
    mapping = baker.make(StoreMapping, _fill_optional=["game"], status=StoreMapping.Status.REJECTED)

    response = admin_authenticated_api_client.post(reverse("games:store-mappings-accept", kwargs={"pk": mapping.pk}))

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_reject_records_reason_and_reviewer(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
) -> None:
    """Rejecting stores the reviewer and the optional reason."""
    mapping = baker.make(StoreMapping, _fill_optional=["game"], status=StoreMapping.Status.PENDING)

    response = admin_authenticated_api_client.post(
        reverse("games:store-mappings-reject", kwargs={"pk": mapping.pk}),
        {"rejection_reason": "Wrong edition"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    mapping.refresh_from_db()
    assert (mapping.status, mapping.reviewed_by, mapping.rejection_reason) == (
        StoreMapping.Status.REJECTED,
        admin_user_fixture,
        "Wrong edition",
    )


@pytest.mark.django_db()
@pytest.mark.parametrize("reason", ["x" * 501, ["not", "a", "string"]])
def test_reject_rejects_invalid_reason(admin_authenticated_api_client: APIClient, reason: object) -> None:
    """An overlong or non-string reason is a validation error and leaves the mapping pending."""
    mapping = baker.make(StoreMapping, _fill_optional=["game"], status=StoreMapping.Status.PENDING)

    response = admin_authenticated_api_client.post(
        reverse("games:store-mappings-reject", kwargs={"pk": mapping.pk}),
        {"rejection_reason": reason},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    mapping.refresh_from_db()
    assert mapping.status == StoreMapping.Status.PENDING


@pytest.mark.django_db()
def test_reject_only_pending(admin_authenticated_api_client: APIClient) -> None:
    """A mapping that is not pending cannot be rejected."""
    mapping = baker.make(StoreMapping, _fill_optional=["game"], status=StoreMapping.Status.ACCEPTED)

    response = admin_authenticated_api_client.post(reverse("games:store-mappings-reject", kwargs={"pk": mapping.pk}))

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_admin_creates_accepted_mapping_superseding_previous(
    admin_authenticated_api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
) -> None:
    """A mapping created by an admin is accepted at once; the previous accepted and pending ones are rejected."""
    game, old_game = baker.make(Game, _quantity=2)
    old = baker.make(StoreMapping, platform="gog", store_id="7", game=old_game, status=StoreMapping.Status.ACCEPTED)
    pending = baker.make(
        StoreMapping,
        _fill_optional=["game"],
        platform="gog",
        store_id="7",
        submitted_by=user_fixture,
        status="pending",
    )

    response = admin_authenticated_api_client.post(
        reverse("games:store-mappings-list"),
        {"platform": "gog", "store_id": "7", "store_title": "Hades", "game": game.pk},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    created = StoreMapping.objects.get(pk=response.json()["id"])
    assert (created.status, created.game, created.submitted_by, created.reviewed_by) == (
        StoreMapping.Status.ACCEPTED,
        game,
        admin_user_fixture,
        admin_user_fixture,
    )
    old.refresh_from_db()
    pending.refresh_from_db()
    assert old.status == pending.status == StoreMapping.Status.REJECTED
    assert StoreMapping.objects.filter(platform="gog", store_id="7", status=StoreMapping.Status.ACCEPTED).count() == 1


@pytest.mark.django_db()
def test_admin_create_validates_input(admin_authenticated_api_client: APIClient) -> None:
    """A missing game or an unknown platform is a 400."""
    url = reverse("games:store-mappings-list")

    assert admin_authenticated_api_client.post(
        url,
        {"platform": "gog", "store_id": "1"},
        format="json",
    ).status_code == (status.HTTP_400_BAD_REQUEST)
    game: Game = baker.make(Game)
    assert admin_authenticated_api_client.post(
        url,
        {"platform": "xbox", "store_id": "1", "game": game.pk},
        format="json",
    ).status_code == (status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db()
def test_admin_marks_store_item_as_not_a_game(
    admin_authenticated_api_client: APIClient,
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """An accepted not-a-game mapping makes imports skip the item, even one IGDB links to a game."""
    game: Game = baker.make(Game)
    external = baker.make(
        ExternalGame,
        external_game_source=baker.make(ExternalGameSource, name="Steam", name_en="Steam"),
        external_id="999",
    )
    game.external_games.add(external)
    url = reverse("games:store-mappings-list")

    response = admin_authenticated_api_client.post(
        url,
        {"platform": "steam", "store_id": "999", "store_title": "Soundtrack", "not_a_game": True},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert (body["not_a_game"], body["game"], body["status"]) == (True, None, "accepted")

    api_client.force_authenticate(user=user_fixture)
    imported = api_client.post(
        reverse("games:game-lists-store-import"),
        {"entries": [{"platform": "steam", "store_id": "999", "title": "Soundtrack", "wishlisted": False}]},
        format="json",
    ).json()
    assert [item["store_id"] for item in imported["skipped"]] == ["999"]
    assert imported["imported"] == imported["already_added"] == imported["unmatched"] == []
    assert not GameList.objects.filter(user=user_fixture).exists()


@pytest.mark.django_db()
def test_admin_create_rejects_game_together_with_not_a_game(admin_authenticated_api_client: APIClient) -> None:
    """A mapping is either to a game or not a game, never both."""
    game: Game = baker.make(Game)

    response = admin_authenticated_api_client.post(
        reverse("games:store-mappings-list"),
        {"platform": "gog", "store_id": "1", "game": game.pk, "not_a_game": True},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_user_proposes_not_a_game_applies_to_them_until_accepted(
    api_client: APIClient,
    admin_user_fixture: UserModel,
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """A user's not-a-game proposal is pending, skips the item for them only, and replaces their game pick."""
    game: Game = baker.make(Game)
    external = baker.make(
        ExternalGame,
        external_game_source=baker.make(ExternalGameSource, name="GOG", name_en="GOG"),
        external_id="55",
    )
    game.external_games.add(external)
    entry = {"platform": "gog", "store_id": "55", "title": "Soundtrack", "wishlisted": False}
    api_client.force_authenticate(user=user_fixture)

    response = api_client.post(
        reverse("games:game-lists-store-not-a-game"),
        {"entries": [{"platform": "gog", "store_id": "55", "store_title": "Soundtrack"}]},
        format="json",
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    mapping = StoreMapping.objects.get(platform="gog", store_id="55")
    assert (mapping.status, mapping.not_a_game, mapping.game, mapping.submitted_by) == (
        StoreMapping.Status.PENDING,
        True,
        None,
        user_fixture,
    )
    url = reverse("games:game-lists-store-import")
    assert [i["store_id"] for i in api_client.post(url, {"entries": [entry]}, format="json").json()["skipped"]] == [
        "55",
    ]
    api_client.force_authenticate(user=other_user_fixture)
    assert api_client.post(url, {"entries": [entry]}, format="json").json()["skipped"] == []

    api_client.force_authenticate(user=admin_user_fixture)
    api_client.post(reverse("games:store-mappings-accept", args=[mapping.pk]))
    api_client.force_authenticate(user=other_user_fixture)
    assert [i["store_id"] for i in api_client.post(url, {"entries": [entry]}, format="json").json()["skipped"]] == [
        "55",
    ]


@pytest.mark.django_db()
def test_user_not_a_game_requires_authentication_and_entries(api_client: APIClient, user_fixture: UserModel) -> None:
    """The endpoint needs a user and at least one entry."""
    url = reverse("games:game-lists-store-not-a-game")
    assert api_client.post(url, {"entries": []}, format="json").status_code == status.HTTP_401_UNAUTHORIZED
    api_client.force_authenticate(user=user_fixture)
    assert api_client.post(url, {"entries": []}, format="json").status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_store_link_maps_listed_game_and_appends_owned_store_only(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Linking a store entry to a listed game records a pending mapping and only appends the owned store."""
    from game_list.games.models import GameListStatus, GameMedia  # noqa: PLC0415

    game, wishlisted_game, unlisted = baker.make(Game, _quantity=3)
    gog, _ = GameMedia.objects.get_or_create(name_en="GOG", defaults={"name": "GOG"})
    entry = baker.make(GameList, user=user_fixture, game=game, status=GameListStatus.COMPLETED, score=9)
    wishlisted_entry = baker.make(GameList, user=user_fixture, game=wishlisted_game)
    api_client.force_authenticate(user=user_fixture)

    def item(store_id: str, linked: Game, *, wishlisted: bool = False) -> dict[str, object]:
        return {"platform": "gog", "store_id": store_id, "title": "T", "wishlisted": wishlisted, "game": linked.pk}

    response = api_client.post(
        reverse("games:game-lists-store-link"),
        {"entries": [item("1", game), item("2", wishlisted_game, wishlisted=True), item("3", unlisted)]},
        format="json",
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    entry.refresh_from_db()
    assert (entry.status, entry.score, list(entry.owned_on.all())) == (GameListStatus.COMPLETED, 9, [gog])
    assert wishlisted_entry.owned_on.count() == 0
    assert set(StoreMapping.objects.values_list("store_id", flat=True)) == {"1", "2"}
    assert not GameList.objects.filter(user=user_fixture, game=unlisted).exists()


@pytest.mark.django_db()
def test_store_link_requires_authentication_and_entries(api_client: APIClient, user_fixture: UserModel) -> None:
    """The endpoint needs a user and at least one entry."""
    url = reverse("games:game-lists-store-link")
    assert api_client.post(url, {"entries": []}, format="json").status_code == status.HTTP_401_UNAUTHORIZED
    api_client.force_authenticate(user=user_fixture)
    assert api_client.post(url, {"entries": []}, format="json").status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_nintendo_game_media_is_seeded() -> None:
    """The migrations seed the Nintendo eShop game media."""
    from game_list.games.models import GameMedia  # noqa: PLC0415

    assert GameMedia.objects.filter(name_en="Nintendo eShop").exists()


@pytest.mark.django_db()
def test_bulk_create_records_a_mapping_for_every_store_ref(api_client: APIClient, user_fixture: UserModel) -> None:
    """An item carrying several store references records one pending mapping for each."""
    game: Game = baker.make(Game)
    api_client.force_authenticate(user=user_fixture)
    item = {
        "game": game.pk,
        "status": "PTP",
        "store_refs": [
            {"platform": "steam", "store_id": "1", "store_title": "Hades"},
            {"platform": "gog", "store_id": "2", "store_title": "Hades"},
        ],
    }

    api_client.post(reverse(BULK_CREATE_URL), [item], format="json")

    assert set(StoreMapping.objects.values_list("platform", "store_id")) == {("steam", "1"), ("gog", "2")}
