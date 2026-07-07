# MyGameList

A backend service for tracking, rating, and reviewing video games. Users maintain personal game lists, follow games for release notifications, and interact socially through friendships.

## Language

**Dictionary Model**:
A named reference/lookup entity whose primary value is its human-readable name, populated from IGDB or manually. Includes `Genre`, `Platform`, `GameMedia`, `GameMode`, `PlayerPerspective`, `ExternalGameSource`, `Company`, `GameEngine`, `GameType`, and `GameStatus`.
_Avoid_: lookup table, reference data, master data

## Relationships

- A **Dictionary Model** has a canonical English name; Polish translations are optional and fall back to English when absent.
- A **Game** has a language-neutral `slug` always derived from its English `title`.
- A **Game** has many **Translation Suggestions**, targeting its `title_pl` or `summary_pl` fields.

## Glossary

**IGDB Import**:
The process by which games are created or updated in the system by fetching data from the IGDB database. The canonical source of truth for game records. Triggers re-normalization of `search_title`.
_Avoid_: sync, game sync, IGDB sync

**Steam Import**:
The two-step process by which a user imports games from their Steam library into their GameList. Step 1: fetch the user's Steam library by `steam_profile_id` and cross-reference against the local `ExternalGame` records, returning a `matched` list (games known to the system, not yet in the user's GameList) and a `not_found` list (games Steam returned that have no record in the system). Step 2: the user selects from the matched list and submits a bulk-create request to add those games to their GameList. Does not create or modify game records.
_Avoid_: sync, sync from Steam, pull from Steam

**Title Import**:
The two-step process by which a user imports games into their GameList from a pasted list of game titles. Step 1: submit the titles and receive, per input title and in input order, up to three candidate games ranked best-first (empty when nothing matches well enough), each flagged when already on the user's GameList. Step 2: the user picks the correct candidate per title (or marks it as not found) and submits a bulk-create request. Stores nothing itself; does not create or modify game records.
_Avoid_: list import, text import, paste import, manual import

**Translation Suggestion**:
A user-submitted proposal for a new Polish value of a single translatable field (`title_pl` or `summary_pl`) on one `Game`. Always carries the full proposed text for that field, never a partial diff or patch — a typo fix and a full re-translation are the same kind of record, just with more or less textual overlap with the current value. Scoped to `Game.title`/`Game.summary` only, not `GameList.description` (which is per-user personal notes, not a translation target). One suggestion targets exactly one field; fixing the title and proposing a new summary are two separate suggestions.

Lifecycle: `pending` → `accepted` | `rejected` | `withdrawn`. The submitter can withdraw their own suggestion while pending; only an admin (`is_staff`) can accept or reject. Accepting applies the `proposed_value` verbatim to the `Game` field (no editing at accept time) and auto-rejects every other pending suggestion for that same game+field. Rejecting may carry an optional reason. A user may have at most one pending suggestion per game+field, but different users may each have their own pending suggestion for the same game+field simultaneously — the admin chooses among them.

Each suggestion snapshots the field's `current_value` at the moment it was submitted, alongside `proposed_value`. This keeps the before→after accurate for every row permanently, even after later suggestions change the field again.

The Translation Suggestion record IS the history: every row (pending, accepted, rejected, withdrawn) is kept permanently and visible to any authenticated user, alongside who submitted it, who reviewed it, and when. This does not cover direct edits to `title_pl`/`summary_pl` made outside this flow (e.g. straight in Django admin) — those are untracked.
_Avoid_: translation request, translation patch, correction

## Flagged ambiguities

- "dictionary model" applies to `GameType` and `GameStatus` even though their primary fields are named `type` and `status` rather than `name`.
- "description" is ambiguous in casual conversation: `Game.summary` (canonical synopsis) vs. `GameList.description` (per-user personal notes). Translation Suggestions only ever target `Game.summary`.
