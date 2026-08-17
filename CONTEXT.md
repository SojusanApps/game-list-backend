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
- A **Report** targets exactly one of: a User's avatar, a User's username, a `GameReview`, a `TranslationSuggestion`, a `GameList`'s note, or a `Collection` (name and/or description) or `CollectionItem`'s note.
- A **User** can file many **Reports** (as `reported_by`) and have many filed against them (as `reported_user`), but never against their own content.
- Accepting a **Report** always issues exactly one **Warning**; a **User** with 3 **Warnings** is automatically **Banned**.
- A **User**'s `slug` is derived from `username` and is regenerated (with collision-suffixing) whenever the username changes — unlike `Game.slug`/`Company.slug`, which are frozen at creation and never revisited. See [ADR-0003](docs/adr/0003-regenerate-user-and-collection-slugs-on-username-change.md).
- A **Collection**'s `slug` is derived from its owning **User**'s `username` and the Collection's `name`; it is regenerated whenever the owning User's username changes, keeping it in sync.

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

**Compare**:
A side-by-side comparison of two users' `GameList` entries, partitioned into three groups: games both users have (`common`), games only the first user has (`first_user_unique`), and games only the second user has (`second_user_unique`). Matching is by `Game` alone, independent of `status` — a `Completed` entry for one user and a `Plan to Play` entry for the other still count as `common`. Each row exposes the game's identity plus each user's `score` and `status` independently, `null` for whichever user doesn't have the game.
_Avoid_: diff, overlap, sync

**Translation Suggestion**:
A user-submitted proposal for a new Polish value of a single translatable field (`title_pl` or `summary_pl`) on one `Game`. Always carries the full proposed text for that field, never a partial diff or patch — a typo fix and a full re-translation are the same kind of record, just with more or less textual overlap with the current value. Scoped to `Game.title`/`Game.summary` only, not `GameList.description` (which is per-user personal notes, not a translation target). One suggestion targets exactly one field; fixing the title and proposing a new summary are two separate suggestions.

Lifecycle: `pending` → `accepted` | `rejected` | `withdrawn`. The submitter can withdraw their own suggestion while pending; only an admin (`is_staff`) can accept or reject. Accepting applies the `proposed_value` verbatim to the `Game` field (no editing at accept time) and auto-rejects every other pending suggestion for that same game+field. Rejecting may carry an optional reason. A user may have at most one pending suggestion per game+field, but different users may each have their own pending suggestion for the same game+field simultaneously — the admin chooses among them.

Each suggestion snapshots the field's `current_value` at the moment it was submitted, alongside `proposed_value`. This keeps the before→after accurate for every row permanently, even after later suggestions change the field again.

The Translation Suggestion record IS the history: every row (pending, accepted, rejected, withdrawn) is kept permanently and visible to any authenticated user, alongside who submitted it, who reviewed it, and when. This does not cover direct edits to `title_pl`/`summary_pl` made outside this flow (e.g. straight in Django admin) — those are untracked.
_Avoid_: translation request, translation patch, correction

**Report**:
A user's flag that a specific piece of another user's content — their avatar, their username, a `GameReview`, a `TranslationSuggestion`, a `GameList` note, or a `Collection`/`CollectionItem` note — violates the rules. Always snapshots the offending text at submission time (`reported_value`), since the live content is mutable and may be edited or already gone by the time an admin reviews it. Avatar reports carry no `reported_value` (there's no text to snapshot) — the admin judges from the live gravatar and the reporter's free-text reason. Lifecycle: `pending` → `accepted` | `rejected`, decided only by an admin (`is_staff`). A user may have at most one pending report per target; different users may each report the same target independently. Visible only to admins and the reporter who filed it — never to the reported user.
_Avoid_: complaint, flag (as a noun), ticket

**Warning**:
One strike issued automatically and exactly once whenever a **Report** is accepted — there is no "accept without warning." Links back to the **Report** that caused it, so a user's moderation history is fully reconstructable. A **User** accumulating 3 **Warnings** is automatically **Banned**; this is a mechanical side effect of the 3rd Warning being created, not a separate admin decision. Implemented as the `ModerationWarning` model — not `Warning`, to avoid shadowing the Python builtin exception class of that name.
_Avoid_: strike, violation, infraction

**Banned** (`User.is_banned`):
A permanent (no un-ban in this feature's scope), automatic state reached at the 3rd **Warning**. A Banned user is functionally unrestricted — they can still write reviews, notes, translation suggestions, collections, everything — the ban has no effect on write permissions. Its only effect is on read visibility: every other user (not the Banned user themself, not an admin) sees the moderation placeholder in place of that user's text, avatar, and username, everywhere, regardless of whether any individual piece of content was ever reported.
_Avoid_: suspended, deactivated, blocked (this is unrelated to `is_active`, which gates login and is untouched by banning)

**Moderated content** (`is_moderated`):
A per-object flag (on `GameReview`, `GameList`, `Collection`, `CollectionItem`, `TranslationSuggestion`) or per-field flag on `User` (`has_moderated_avatar`, `has_moderated_username`), set permanently when that specific object's **Report** is accepted. Never auto-clears, even if the owner edits the content afterward. Masking is enforced only at the serializer: the live field is never overwritten or deleted, so "moderated" and "banned" are read-time visibility rules, not data mutations. The moderated owner and any admin always see the real value; everyone else sees the shared placeholder text. `has_moderated_avatar` is the one exception — once set, the avatar is hidden from literally everyone, including its owner, because avatar reports exist specifically for illegal-content cases.
_Avoid_: deleted, removed, hidden (as a synonym for the flag itself — "hidden" describes the visibility effect, not the mechanism)

**Identity**:
The authenticated principal as Keycloak knows it — the token's `sub` claim plus whatever other claims it carries (`nickname`, `email`, `email_verified`). Not the same thing as a `User`.
_Avoid_: token, claims (as a synonym for the concept itself — those are how an Identity is carried, not the Identity)

**User** (sharpened against Identity):
The backend's own account record. Resolved _from_ an Identity via the Keycloak authentication class — never assumed to already exist for a given Identity, always looked up or provisioned by `sub`. See [ADR-0006](docs/adr/0006-provisioning-in-authentication-class.md).

## Flagged ambiguities

- "dictionary model" applies to `GameType` and `GameStatus` even though their primary fields are named `type` and `status` rather than `name`.
- "description" is ambiguous in casual conversation: `Game.summary` (canonical synopsis) vs. `GameList.description` (per-user personal notes). Translation Suggestions only ever target `Game.summary`.
- "description" is further overloaded by `Collection.description` and `CollectionItem.description` — a third and fourth distinct field, both reportable/moderatable, neither related to `Game.summary` or `GameList.description`.
- A `Report` targeting a `Collection` covers both `name` and `description` as one unit (one `is_moderated` flag) — the reporter's free-text reason is what tells the admin which field was actually the problem, the system doesn't track that distinction structurally.
- Reporting an already-`accepted` `TranslationSuggestion` and having that report accepted only moderates the `TranslationSuggestion` audit row — it deliberately does **not** revert `Game.title_pl`/`summary_pl` if the bad value was already copied onto the `Game`. Known gap, out of scope by choice.
