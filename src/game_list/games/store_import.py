"""Matching of store library entries (from the browser extension) against games and Store Mappings."""

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from game_list.games.models import (
    ExternalGame,
    Game,
    GameList,
    GameListStatus,
    GameMedia,
    StoreMapping,
    StorePlatform,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from game_list.users.models import User

# The single place that ties a store to the IGDB `ExternalGameSource` names it may appear under.
IGDB_SOURCE_NAMES: dict[str, tuple[str, ...]] = {
    StorePlatform.STEAM: ("Steam",),
    StorePlatform.GOG: ("GOG",),
    StorePlatform.EPIC: ("Epic Games", "Epic Games Store"),
    StorePlatform.PLAYSTATION: ("Playstation Store US", "PlayStation Store US", "PlayStation Store"),
    StorePlatform.NINTENDO: ("Nintendo eShop",),
}

# The `GameMedia` (English name) a game owned on the store is recorded under in `GameList.owned_on`.
GAME_MEDIA_NAMES: dict[str, str] = {
    StorePlatform.STEAM: "Steam",
    StorePlatform.GOG: "GOG",
    StorePlatform.EPIC: "Epic Games Store",
    StorePlatform.PLAYSTATION: "PlayStation Store",
    StorePlatform.NINTENDO: "Nintendo eShop",
}

StoreKey = tuple[str, str]


@dataclass(frozen=True)
class StoreEntry:
    """One game of a store library, as sent by the browser extension."""

    platform: str
    store_id: str
    title: str
    wishlisted: bool

    @property
    def key(self) -> StoreKey:
        """The (platform, store id) pair identifying the game on its store."""
        return (self.platform, self.store_id)


def _igdb_matches(keys: set[StoreKey]) -> dict[StoreKey, set[int]]:
    """Games linked to each key through IGDB's external games."""
    matches: dict[StoreKey, set[int]] = defaultdict(set)
    for platform in {platform for platform, _ in keys}:
        ids = {store_id for key_platform, store_id in keys if key_platform == platform}
        rows = ExternalGame.objects.filter(
            external_game_source__name_en__in=IGDB_SOURCE_NAMES[platform],
            external_id__in=ids,
            games__isnull=False,
        ).values_list("external_id", "games__id")
        for external_id, game_id in rows:
            matches[(platform, external_id)].add(game_id)
    return matches


def _mapping_matches(keys: set[StoreKey], user: User, *, accepted: bool) -> dict[StoreKey, set[int]]:
    """Games linked to each key by accepted Store Mappings, or by the user's own pending ones."""
    condition = Q()
    for platform, store_id in keys:
        condition |= Q(platform=platform, store_id=store_id)
    if accepted:
        scope = Q(status=StoreMapping.Status.ACCEPTED)
    else:
        scope = Q(status=StoreMapping.Status.PENDING, submitted_by=user)
    matches: dict[StoreKey, set[int]] = defaultdict(set)
    if not keys:
        return matches
    for platform, store_id, game_id in StoreMapping.objects.filter(condition, scope, not_a_game=False).values_list(
        "platform",
        "store_id",
        "game_id",
    ):
        matches[(platform, store_id)].add(game_id)
    return matches


def _not_a_game_keys(keys: set[StoreKey], user: User) -> set[StoreKey]:
    """Keys marked as not a game by an accepted Store Mapping, or by the user's own pending one."""
    if not keys:
        return set()
    condition = Q()
    for platform, store_id in keys:
        condition |= Q(platform=platform, store_id=store_id)
    scope = Q(status=StoreMapping.Status.ACCEPTED) | Q(status=StoreMapping.Status.PENDING, submitted_by=user)
    return set(
        StoreMapping.objects.filter(condition, scope, not_a_game=True).values_list("platform", "store_id"),
    )


def resolve_games(keys: Iterable[StoreKey], user: User) -> dict[StoreKey, int]:
    """Map each store key to exactly one game id; keys with no match or an ambiguous one are left out.

    Resolution order is IGDB external games, then accepted Store Mappings, then the user's own pending
    mappings. The first source that knows the key decides: if it points at several games, the key is ambiguous.
    """
    pending = set(keys)
    resolved: dict[StoreKey, int] = {}
    lookups: tuple[Callable[[set[StoreKey]], dict[StoreKey, set[int]]], ...] = (
        _igdb_matches,
        lambda remaining: _mapping_matches(remaining, user, accepted=True),
        lambda remaining: _mapping_matches(remaining, user, accepted=False),
    )
    for lookup in lookups:
        if not pending:
            break
        matches = lookup(pending)
        for key, game_ids in matches.items():
            if len(game_ids) == 1:
                resolved[key] = next(iter(game_ids))
            pending.discard(key)
    return resolved


def game_media_ids() -> dict[str, int]:
    """The `GameMedia` id of each store, for the stores whose media row exists."""
    by_name = dict(GameMedia.objects.filter(name_en__in=GAME_MEDIA_NAMES.values()).values_list("name_en", "id"))
    return {platform: by_name[name] for platform, name in GAME_MEDIA_NAMES.items() if name in by_name}


@dataclass
class ImportOutcome:
    """The result of auto-importing the matched entries of one store sync."""

    imported: list[tuple[StoreEntry, int]]
    already_added: list[tuple[StoreEntry, int]]
    unmatched: list[StoreEntry]
    skipped: list[StoreEntry]


def _owned_media_by_game(entries: list[StoreEntry], resolved: dict[StoreKey, int]) -> dict[int, set[int]]:
    """The `GameMedia` ids to record per matched game, from the entries the user owns (not just wishlisted)."""
    media = game_media_ids()
    owned_media: dict[int, set[int]] = defaultdict(set)
    for entry in entries:
        game_id = resolved.get(entry.key)
        if game_id is not None and not entry.wishlisted and entry.platform in media:
            owned_media[game_id].add(media[entry.platform])
    return owned_media


def import_entries(entries: list[StoreEntry], user: User) -> ImportOutcome:
    """Add matched entries to the user's game list and report what happened to every entry.

    New games are added as plan-to-play and unscored, with `owned_on` set to the store only when the user owns the
    game. For a game already on the list only the store is appended to `owned_on`; nothing else is touched.
    """
    keys = {entry.key for entry in entries}
    not_a_game = _not_a_game_keys(keys, user)
    resolved = resolve_games(keys - not_a_game, user)
    owned_media = _owned_media_by_game(entries, resolved)

    game_lists = {gl.game_id: gl for gl in GameList.objects.filter(user=user, game_id__in=set(resolved.values()))}
    on_list = set(game_lists)
    outcome = ImportOutcome(imported=[], already_added=[], unmatched=[], skipped=[])
    for entry in entries:
        if entry.key in not_a_game:
            outcome.skipped.append(entry)
            continue
        game_id = resolved.get(entry.key)
        if game_id is None:
            outcome.unmatched.append(entry)
            continue
        if game_id not in game_lists:
            game_lists[game_id] = GameList.objects.create(
                user=user,
                game_id=game_id,
                status=GameListStatus.PLAN_TO_PLAY,
            )
        (outcome.already_added if game_id in on_list else outcome.imported).append((entry, game_id))

    for game_id, media_ids in owned_media.items():
        if media_ids:
            game_lists[game_id].owned_on.add(*media_ids)
    return outcome


@dataclass(frozen=True)
class StoreLink:
    """A store entry the user matched by hand to a game that is already on their game list."""

    entry: StoreEntry
    game: Game


def link_listed_games(links: list[StoreLink], user: User) -> int:
    """Record the user's pick as a pending Store Mapping and append the store to `owned_on` of listed games.

    Nothing else of the game list entry is touched, and a game that is not on the user's list is ignored.
    Returns the number of links applied.
    """
    media = game_media_ids()
    game_lists = {
        gl.game_id: gl for gl in GameList.objects.filter(user=user, game_id__in={link.game.pk for link in links})
    }
    applied = 0
    for link in links:
        game_list = game_lists.get(link.game.pk)
        if game_list is None:
            continue
        submit_pending_mapping(user, link.entry.key, link.entry.title, link.game)
        if not link.entry.wishlisted and link.entry.platform in media:
            game_list.owned_on.add(media[link.entry.platform])
        applied += 1
    return applied


SUPERSEDED_REASON = "Superseded by mapping #%(id)s."
REPLACED_REASON = "Another mapping was accepted for this store id (#%(id)s)."


def submit_pending_mapping(user: User, entry: StoreKey, store_title: str, game: Game | None) -> StoreMapping | None:
    """Record the user's own pick of a game for a store id as a pending Store Mapping.

    A None game proposes the store item as not a game. Returns None when nothing needs recording: an accepted
    mapping already knows the store id, or IGDB already links it to the picked game. A previous pending mapping of
    the same user for the same store id is replaced.
    """
    platform, store_id = entry
    if StoreMapping.objects.filter(platform=platform, store_id=store_id, status=StoreMapping.Status.ACCEPTED).exists():
        return None
    if game is not None and game.pk in _igdb_matches({entry}).get(entry, set()):
        return None
    mapping, _ = StoreMapping.objects.update_or_create(
        platform=platform,
        store_id=store_id,
        submitted_by=user,
        status=StoreMapping.Status.PENDING,
        defaults={"game": game, "not_a_game": game is None, "store_title": store_title},
    )
    return mapping


def _reject_rivals(mapping: StoreMapping, admin: User) -> None:
    """Reject the accepted mapping (superseded) and every other pending one for the same store id."""
    now = timezone.now()
    rivals = StoreMapping.objects.filter(platform=mapping.platform, store_id=mapping.store_id).exclude(pk=mapping.pk)
    rivals.filter(status=StoreMapping.Status.ACCEPTED).update(
        status=StoreMapping.Status.REJECTED,
        reviewed_by=admin,
        reviewed_at=now,
        rejection_reason=SUPERSEDED_REASON % {"id": mapping.pk},
    )
    rivals.filter(status=StoreMapping.Status.PENDING).update(
        status=StoreMapping.Status.REJECTED,
        reviewed_by=admin,
        reviewed_at=now,
        rejection_reason=REPLACED_REASON % {"id": mapping.pk},
    )


def accept_mapping(mapping: StoreMapping, admin: User) -> StoreMapping:
    """Make a pending mapping the one accepted mapping of its store id, superseding the previous one."""
    with transaction.atomic():
        _reject_rivals(mapping, admin)
        mapping.status = StoreMapping.Status.ACCEPTED
        mapping.reviewed_by = admin
        mapping.reviewed_at = timezone.now()
        mapping.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return mapping


def create_accepted_mapping(
    admin: User,
    platform: str,
    store_id: str,
    store_title: str,
    game: Game | None,
) -> StoreMapping:
    """Create an admin-made mapping, accepted at once, superseding the previous one.

    A None game marks the store item as not a game, so imports skip it.
    """
    with transaction.atomic():
        mapping, _ = StoreMapping.objects.update_or_create(
            platform=platform,
            store_id=store_id,
            submitted_by=admin,
            status=StoreMapping.Status.PENDING,
            defaults={"game": game, "not_a_game": game is None, "store_title": store_title},
        )
        return accept_mapping(mapping, admin)
