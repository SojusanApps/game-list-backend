# CHANGELOG

> Date format is DD.MM.YYYY.

## v. [5.0.0] - 17.08.2026

* Migrated authentication from self-issued `SimpleJWT` tokens to Keycloak-issued access tokens — a hard cutover, not a dual-accept transition period.
  * New `KeycloakAuthentication` class (`my_game_list/authentication.py`), the sole entry in `DEFAULT_AUTHENTICATION_CLASSES`, validates tokens offline against the realm's JWKS endpoint (`PyJWT`'s `PyJWKClient`, keys cached). Checks `iss` strictly against the configured realm and accepts the expected client id in either the `aud` or `azp` claim, since Keycloak doesn't reliably populate `aud` with the client id unless an audience mapper is configured.
  * `User` gets a new `keycloak_id` field (nullable, unique), storing the token's `sub` claim.
  * On every authenticated request, the caller is resolved to a local `User` by `keycloak_id`: a never-seen `sub` provisions a new account (`username` from the token's `nickname` claim, `email` from `email`, unusable password); a known `sub` has its `username` reconciled from the current `nickname` claim on every call, resolving a collision with another user's username via a numeric suffix. Reconciliation also regenerates `User.slug` and every owned `Collection.slug`, matching what the old change-username endpoint used to do.
  * `is_staff` is derived, on every authenticated request, from whether the token's client roles (`resource_access.<KEYCLOAK_CLIENT_ID>.roles`) include `"admin"` — present grants staff, absent revokes it, including on an account that was previously granted `is_staff` some other way (e.g. `createsuperuser`). A resolved `User` with `is_active=False` is still rejected even with an otherwise valid token, same as before.
  * `gender` is synced from the token's `gender` claim (`"male"`/`"female"`/`"prefer_not_to_say"`) on every request — mapped to `Gender.MALE`/`Gender.FEMALE`, with `"prefer_not_to_say"`, a missing claim, or an unrecognized value all mapping to blank.
  * A never-seen `sub` whose token asserts a verified email matching an existing, not-yet-linked `User` (e.g. an admin account bootstrapped via `createsuperuser`) is linked to that account instead of failing — fixes a 500 on the duplicate-email `IntegrityError` this used to raise. An unverified email colliding with an existing account fails cleanly with `401` instead.
  * New settings: `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_AUDIENCE`, `KEYCLOAK_CLIENT_ID`.
  * Added a `drf-spectacular` authentication extension (`KeycloakAuthenticationScheme`) so the generated OpenAPI schema correctly documents the new Bearer scheme instead of silently losing auth info for every endpoint.
* Added `GET /user/users/me/` — returns the authenticated caller's own account, in the same shape as the owner-view of `GET /user/users/{id}/`.
* Removed the pre-Keycloak self-service authentication surface, now that the frontend has no login/register UI of its own and Keycloak is the sole token issuer: self-registration (`POST /user/users/`), `POST /token/`, `POST /token/refresh/`, `POST /user/users/change-password/`, and `POST /user/users/change-username/`. Dropped the now-unused `djangorestframework-simplejwt` dependency.
* Fixed a pre-existing bug: `email` was visible to any authenticated viewer on `GET /user/users/` and `GET /user/users/{id}/`, not just the account owner, contradicting those endpoints' own documented behavior. Now restricted to the account owner and staff, matching the existing `warning_count` visibility rule.
* Fixed `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` being a bare string instead of a tuple, which crashes DRF's default `get_permissions()` — never hit before since every `ViewSet` already set its own `permission_classes` explicitly, until `UserViewSet` started relying on the default after its registration-only `get_permissions()` override was removed.
* Updated dependencies.

## v. [4.27.0] - 21.07.2026

* Added a `GameList` compare endpoint: `GET /game-lists/{first_user_id}/compare/{second_user_id}/` on `GameListViewSet` (`IsAuthenticated`, unpaginated). Partitions the two users' game lists into `common` (games both have, matched by `Game` regardless of each user's individual `status`), `first_user_unique`, and `second_user_unique`, each ordered alphabetically by title. Each row carries `game_id`/`game_slug`/`title`/`game_cover_image` plus `first_user_score`/`first_user_status`/`first_user_status_code` and the equivalent `second_user_*` fields (`null` when that user doesn't have the game). Comparing a user against themselves returns `400`; a nonexistent user ID returns `404`.

## v. [4.26.0] - 16.07.2026

* Added self-service username and password change endpoints to `UserViewSet` (`/user/users/`), both self-service only (operate on `request.user`, no way to target another account) and fully documented via `@extend_schema` (correct request/response bodies instead of the ViewSet's default `User` schema).
  * `POST /change-username/` — validates the new username against the same format/uniqueness rules as registration and rejects a no-op (same-as-current) submission. Regenerates `User.slug`, and every slug of the user's owned `Collection`s, from the new username, resolving any collision with a numeric suffix. Returns the updated user (`UserDetailSerializer`).
  * `POST /change-password/` — requires the current password for re-verification, validates the new password with the same `django_validate_password` rules used at registration, and requires a matching confirmation. Returns `204 No Content`. Does not invalidate already-issued tokens on other devices.
* Extracted a shared `generate_unique_slug` helper (`my_game_list/slugs.py`) from `Collection.save()`'s existing collision-suffixing logic, and wired it into `User.save()` too — fixing a pre-existing latent bug where `User.save()` never handled slug collisions at all (distinct valid usernames can collide once `.`/`@`/`+` are stripped and case is folded by `slugify()`).
* Fixed `UserViewSet.get_authenticators()`, which was silently skipping authentication for *any* `POST` request to the viewset, not just the intended `create`/registration action — harmless while `create` was the only `POST` action, but would have left the new `change-username`/`change-password` actions open with no authentication.

## v. [4.25.0] - 10.07.2026

* Added a user reporting and content moderation system.
  * New `moderation` app with `Report` and `ModerationWarning` models, and endpoints under `/moderation/reports/`.
    * `POST`/`GET` on the list endpoint — any authenticated user can report another user's `avatar`, `username`, `GameReview`, `TranslationSuggestion`, a `GameList` note, a `Collection` (name+description together), or a `CollectionItem` note (`target_type`). A user can't report their own content, and can't file a second pending report against the same target while their first is still pending.
    * Non-staff users only see reports they personally filed; staff see every report. List supports filtering by `id`, `target_type`, `status`, `reported_by`, and `reported_user`.
    * `POST /{id}/accept/` and `POST /{id}/reject/` — admin-only. Accepting flags the target as moderated and issues exactly one `ModerationWarning`; a user's 3rd warning automatically bans them (`User.is_banned`).
    * `reported_by`, `reported_user`, and `reviewed_by` are returned as nested `UserSimpleSerializer` objects.
  * Moderation is enforced entirely at read time — nothing is ever deleted or rewritten. A shared `mask_if_moderated` helper (`moderation/masking.py`) replaces `GameReview.review`, `GameList.description`, `TranslationSuggestion.proposed_value`, `Collection.name`/`description`, `CollectionItem.description`, `User.username`, and `User.gravatar_url` with a placeholder for any viewer who isn't the content's owner or staff.
    * A banned user's content is masked for every other viewer across all of the above, not just the specific items that were reported.
    * A moderated avatar (`User.has_moderated_avatar`) is hidden from literally everyone, including its own owner and staff — the one field with no owner/staff exemption, since avatar reports are for illegal-content cases.
    * Placeholder text respects the request's `Accept-Language` header (previously would have been frozen to whichever language was active at process startup); Polish translations added.
  * Added `warning_count` to `UserDetailSerializer`, restricted to the profile owner and staff (`null` for other viewers) to avoid a public shaming vector.
  * Registered `Report` and `ModerationWarning` in Django admin.
  * Added an `ENUM_NAME_OVERRIDES` entry for `Report.status` (`ReportStatusEnum`) to resolve an OpenAPI enum-naming collision.
  * Filled in missing/fuzzy Polish translations for the new moderation strings in `locale/pl/LC_MESSAGES/django.po`.
* Fixed `GameListViewSet.bulk_create` and `.export` not passing serializer context, which broke `gravatar_url`/`username` masking on those endpoints (caught while wiring moderation into `GameListSerializer`); added `export` test coverage, which previously had none.

## v. [4.24.1] - 08.07.2026

* Added missing `translation.atomic`.

## v. [4.24.0] - 07.07.2026

* Added a `TranslationSuggestion` model and endpoints (`/game/translation-suggestions/`) letting authenticated users propose a corrected Polish `title` or `summary` for a game.
  * `GET`/`POST` on the list endpoint: full history (pending/accepted/rejected/withdrawn) is visible to any authenticated user; creating a suggestion snapshots the game's current value server-side and validates `proposed_value` against the target field's max length.
  * A user can only have one pending suggestion per game+field (enforced by a conditional `UniqueConstraint`), but different users may submit competing suggestions for the same game+field.
  * `POST /{id}/withdraw/` — submitter-only, cancels a pending suggestion.
  * `POST /{id}/accept/` — admin-only, applies the proposed value to the game (via `Game.save()`, so `search_title` recomputes) and auto-rejects sibling pending suggestions for the same game+field.
  * `POST /{id}/reject/` — admin-only, with an optional `rejection_reason`.
  * Accept/reject send a notification to the submitter (new `NotificationCategory.TRANSLATION_SUGGESTION` and matching `NotificationVerb` entries).
  * `game` and `submitted_by`/`reviewed_by` are returned as nested objects (`GameReferenceSerializer`, `UserSimpleSerializer`) on list/retrieve/withdraw/accept/reject responses.
  * Registered in Django admin and added Bruno requests under `Game/translation-suggestion/`.
* Added `ENUM_NAME_OVERRIDES` to `SPECTACULAR_SETTINGS` to resolve an OpenAPI enum-naming collision between `GameList.status` and the new `TranslationSuggestion.status`.
* Filled in missing/fuzzy Polish translations in `locale/pl/LC_MESSAGES/django.po`.

## v. [4.23.0] - 06.07.2026

* Reworked fuzzy title matching to rank results correctly for misspelled queries: `pg_trgm` similarity is now used only to fetch a candidate pool, and Python re-ranks it with Damerau-Levenshtein similarity (`rapidfuzz`), with ties broken by the game's members count.
* Added a title import endpoint (`POST /game-lists/title-import/`) that matches a pasted list of game titles against the catalogue, returning up to 3 candidate games (`id`, `title`, `cover_image_id`, `already_in_list`) per title. Mirrors the two-step Steam import flow: pick matches, then submit them to the existing bulk-create endpoint.

## v. [4.22.0] - 26.06.2026

* Replaced `Makefile` with a `justfile` — migrated task runner from `make` to `just` with the same set of commands.
* Improved fuzzy title search ranking: scoring now uses a weighted blend of `TrigramWordSimilarity` (70%) and `TrigramSimilarity` (30%) instead of word-similarity alone, improving relevance for partial and substring matches.
* Added explicit `url_path` to notification `ViewSet` actions: `unread-count`, `mark-as-read`, `mark-all-as-read`, and `delete-all-read`.

## v. [4.21.2] - 25.06.2026

* Extended `GameListFilterSet` with all game-attribute filters: `title` (fuzzy trigram), `release_date` (range), `publisher`, `developer`, `genres`, `platforms`, `game_type`, `game_status`, `game_engines`, `game_modes`, `player_perspectives`, and `external_games`.
* Updated `extend_schema` for `GameListViewSet` list action to document all new filter parameters.

## v. [4.21.1] - 24.06.2026

* Added `title_en` to `GameSerializer`.

## v. [4.21.0] - 23.06.2026

* Added game list export endpoint (`GET /game-lists/export/`) that returns the authenticated user's full game list as JSON without pagination.

## v. [4.20.3] - 21.06.2026

* Added a nightly Celery periodic task `nightly_igdb_import_and_recalculate` that runs at midnight UTC.
  * Incrementally imports all IGDB data (`platforms`, `genres`, `game_modes`, `player_perspectives`, `game_engines`, `game_types`, `game_statuses`, `external_game_sources`, `external_games`, `companies`, `games`).
  * Recalculates game statistics immediately after a successful import.

## v. [4.20.2] - 19.06.2026

* Replaced manual Docker test setup with `testcontainers`.
  * Removed shell scripts `my-game-list-run-tests.sh`, `my-game-list-run-tests-with-pg.sh`, `wait-for-postgresql.py`, and `colors.sh`.
  * Added `django_db_setup` fixture in `tests/conftest.py` that automatically starts a PostgreSQL container per test worker and runs migrations.
  * Updated `settings/test.py` with a placeholder `DATABASES` config (overridden at runtime by testcontainers).
  * Updated `tox.ini` to call `pytest` directly without shell script wrappers.
  * Removed `services: postgres` from the GitHub Actions CI workflow — testcontainers manages the database in CI as well.

## v. [4.20.1] - 18.06.2026

* Improved game title filter with fuzzy search using PostgreSQL `pg_trgm`.
  * Added `search_title` field to `Game` model — normalized (lowercase, no diacritics, no special characters) concatenation of English and Polish titles.
  * Added GIN index on `search_title` for fast trigram lookups.
  * Filter now supports: case-insensitive matching, diacritic tolerance, partial word matching, word-order independence, and typo tolerance.
  * Results are ordered by similarity score when the title filter is active.
  * IGDB Import updated to populate `search_title` during `bulk_create`.

## v. [4.20.0] - 17.06.2026

* Added steam import endpoint.
* Added game list bulk create endpoint.

## v. [4.19.1] - 21.05.2026

* Updated the docs for better swagger schema generation.

## v. [4.19.0] - 20.05.2026

* Added polish localization.
* Added `member` to collection filters, this allows to get all collection that the user has access to. (his own and with contributor address).
* Increased the number of returned items in the calendar endpoint, per day, to 3.

## v. [4.18.4] - 18.05.2026

* Removed create and delete endpoints from the API for `Company` and `Game` models.

## v. [4.18.3] - 15.05.2026

* Add `is_stuff` to `User` serializers.

## v. [4.18.2] - 07.05.2026

* Add prometheus metrics:
  * `users_registered_total` - Total number of registered users.
  * `game_lists_entries_created_total` - Total number of game list entries created.

## v. [4.18.1] - 07.05.2026

* Add more traces for `requests`, `urllib` and `urllib3`.

## v. [4.18.0] - 05.05.2026

* Add traces with `opentelemetry`.

## v. [4.17.1] - 05.05.2026

* Updated dependencies in requirements.
* Migrated to `psycopg3` from `psycopg2`.

## v. [4.17.0] - 29.04.2026

* Add `slug` filed to `Game`, `Company`, `User` and `Collection` models.
* Updated dependencies in requirements.

## v. [4.16.0] - 24.04.2026

* Add `ExternalGameSource` and `ExternalGame` models.

## v. [4.15.2] - 22.04.2026

* Add `build-and-push.yml` - GitHub Action to build and push the docker images.
* Add `AGENTS.md` - instructions for AI agents to interact with the repository.

## v. [4.15.1] - 21.04.2026

* Add `.editorconfig`.

## v. [4.15.0] - 16.04.2026

* Add `notify_game_releases` - a celery task to create notification about game release to users that have the game in `GameFollow`.

## v. [4.14.1] - 23.03.2026

* Add `last_active` to `User` model.

## v. [4.14.0] - 19.03.2026

* Upgraded PostgreSQL version to `18.3`.
* Changed the celery broker from `regis` to `rabbitmq`.
* Updated dependencies in requirements.

## v. [4.13.2] - 16.03.2026

* Added `category` to the `Notification` model.

## v. [4.13.1] - 12.03.2026

* Simplify `gender` field by removing an option `X - prefer not to say`, a blank option is the same.
* OpenAPI schema adjustments.

## v. [4.13.0] - 11.03.2026

* Added `release-calendar` endpoint for games.
* Added ordering by `release_date` for games.

## v. [4.12.0] - 09.03.2026

* Added new fields to the `GameList` model:
  * `description`,
  * `completed_at`,
  * `started_at`,
  * `playtime`.

## v. [4.11.1] - 04.03.2026

* Added `gravatar_url` to `actor` and `target` in `Notifications` if their model is `User`.

## v. [4.11.0] - 03.03.2026

* Added `random-ptp` endpoint for getting a random plan to play item from the user game list.

## v. [4.10.1] - 23.02.2026

* Add `import_start_timestamp` to IGDB import script.

## v. [4.10.0] - 17.02.2026

* Implemented bulk reorder functionality for collection items with validation and tests

## v. [4.9.1] - 17.02.2026

* Updated dependencies in requirements.

## v. [4.9.0] - 17.02.2026

* Changed the `order` field in collections to be `DecimalField`, as now the items uses fractional order.
* Introduced `CollectionType` model with choices for collection types.
* Updated Collection model to include a type field.
* Enhanced CollectionFilterSet to filter by collection type.
* Added has_tier filter to CollectionItemFilterSet for tier classification.
* Adjusted migrations to reflect changes in the database schema.
* [BREAKING] Updated the collection items reorder endpoint: URL changed from `/collections/{pk}/reorder-items/` to `/collections/{pk}/items/{item_id}/reorder/`, request body changed from an array of items to a single item with `position`, and response changed from `204 No Content` to `200 OK` with an `order` field.

## v. [4.8.0] - 30.01.2026

* Added Bruno endpoints for collections.
* Added `Collections` app.

## v. [4.7.1] - 21.01.2026

* Fix the m2m relation import in the `import_data_from_igdb.py` script for games objects.

## v. [4.7.0] - 01.01.2026

* Improvements to game queries to make them faster.
* Added additional information to the Game model:
  * `GameEngine`
  * `GameMode`
  * `PlayerPerspective`
  * `GameType`
  * `GameStatus`
* Updated the `Game` list endpoint to include the game status and type.
* Updated the `Game` retrieve endpoint to include the new data.
* Updated the `Game` filters.

## v. [4.6.0] - 28.12.2025

* Changed the `User` model `str` method.
* Removed `all-values` endpoints.
* Added `CompanyGameSerializer` and `CompanyDetailSerializer`.
* Fixed the ordering for the `latest_game_updates` in the user details.

## v. [4.5.0] - 26.12.2025

* Added `notifications` application.
* Added a notification when user send/accepts the friend request.

## v. [4.4.0] - 25.12.2025

* Updated the Python version to 3.14.
* Updated dependencies in requirements.

## v. [4.3.0] - 21.12.2025

* Added `igdb_updated_at` to models:
  * `Game`, `Platform`, `Genre` and `Company`
* Improved the IGDB import script to be based on the `updated_at`, so only the newest updates will be processed.
* Move `dev` dependencies into `[dependency-groups]`.

## v. [4.2.5] - 26.11.2025

* Added [django-tui](https://github.com/anze3db/django-tui) - a package that adds a terminal user interface for django commands.
* Updated dependencies in requirements.

## v. [4.2.4] - 03.09.2025

* Migrate to [uv](https://docs.astral.sh/uv) package manager.
* Added a new settings file for mypy type checker.
* Update Docker files to be compatible with uv package manager.
* Divided the tox commands into separate envs.
* Added [typer](https://github.com/fastapi/typer) for command line interface.
  * Changed `my-game-list-build.py` script to use `typer`.
* Updated the GitHub Action configuration to work with uv.
* Upgraded PostgreSQL version to `18.0`.
* Changed the GitHub Action to use commit SHA instead of tags.

## v. [4.2.3] - 28.08.2025

* Updated dependencies in requirements.
* Adjust code typing to fix mypy issues.
* Updated SonarQube Github action scanner.
* Updated the prometheus metrics endpoint to accept only GET request.

## v. [4.2.2] - 11.02.2025

* Updated dependencies in requirements.
* Added missing migration.

## v. [4.2.1] - 10.02.2025

* Added a new make command (`generate_openapi`) to generate the `openapi.json` file.
* Fixed the openapi schema using the `drf-spectacular`.
* Changed the `ApiVersion` to return a structured output instead of raw string.

## v. [4.2.0] - 14.01.2025

* Added `GameMedia` model in `game` app.
* Added `owned_on` to `GameList` model.1

## v. [4.1.3] - 05.12.2024

* Added base class for IGDB models `IGDBModel`.
* Improvements to IGDB integrations.

## v. [4.1.2] - 02.11.2024

* Changed the way of handling the source code, from individual file for each object to a single one for all.

## v. [4.1.1] - 02.11.2024

* Cleanup in `docker-compose.yml`:
  * Use depends on condition for waiting for database instead of custom script,
  * Fix running the application as non-root user.

## v. [4.1.0] - 11.09.2024

* Removed the `avatar` field from the `User` model.
* For avatars now will be used `Gravatar`.
* Removed the `FileSizeValidator` as it is no longer needed.
* Removed the environment variable `MGL_LIMIT_FILE_SIZE` as it is no longer needed.

## v. [4.0.0] - 10.09.2024

* Integrated with the IGDB database.
* Removed the development example data as the process is changed in favor of the IGDB database.
* Updated dependencies in requirements.
* Removed the `requirements-deploy.txt` file.
* Updated `Bruno` endpoints.
* Fixed `ruff` configuration.
* Added new environment variables to `example.env` (`IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET`).
* Added new model `Company`.
* Removed old models for `Developer` and `Publisher`, they are now in the new `Company` model.
* Changed the `Genre`, `Game`, `Platform` and `Company` models to be compatible with IGDB data.
* Changed the `game_cover_image` field in the `GameListSerializer` to be `CharField` instead of `FileField`.
* Added `igdb_id` field to the `Game`, `Company`, `Genre` and `Platform` models, as those are now objects integrated with external IGDB database.
* Renamed the `dictionary` field into `summary` in the `Game` model.
* Added `abbreviations` field to the `Platform` model.
* Removed the `django_cleanup` dependency.
* Updated tests to reflect the changes made to models.
* Updated dependencies in the `pre-commit` configuration.

## v. [3.3.0] - 12.06.2024

* Added new development data regarding the developers and publishers.
* Added a new field for the company logo for developers and publishers.

## v. [3.2.0] - 15.05.2024

* Added `Bruno` endpoints for development.
* Added `status_code` to game list endpoints.
* Added `game_id` to the `GameListSerializer`.
* Removed `logged_in_user` action for the `user` endpoint.

## v. [3.1.0] - 13.05.2024

* Fixed `GameListSerializer` to return the cover image url.
* Fixed `UserDetailSerializer` to return the image urls for nested objects.
* Added `logged_in_user` - new action for the `user` endpoint to get the details of the logged in user.

## v. [3.0.1] - 10.05.2024

* Calculation of the rank position is fixed. Right now the average store will have `0` instead of `none` when there is no scores for the game.
* Added `load_development_data` - new make command to load development data.

## v. [3.0.0] - 09.05.2024

* Changed `BinaryField` to `ImageField` for `game_cover` and `avatar`.
* Added `average_score`, `scores_count`, `rank_position`, `members_count`, and `popularity` to `Game` models.
* Added new dependency `django-cleanup` to automatically cleanup media files.
* Added new setting `LIMIT_FILE_SIZE`, to control the size of the uploaded images.
* Added `FileSizeValidator` - validator of the uploaded file size.
* Added development setting for working with media files.
* Added ordering settings for `Game` views.
* Added `GameQuerySet`.

## v. [2.2.0] - 03.04.2024

* Updated few models and serializers:
  * GameReview
  * GameList
  * User
* Moved `score` from `GameReview` to `GameList`.
* Added `GameListCreateSerializer`.
* Added `Gender` to `User` model.

## v. [2.1.3] - 06.03.2024

* Added user details to GameReview endpoint.

## v. [2.1.2] - 21.02.2024

* Updated the Python version to 3.12.
* Enabled coverage reporting in the SonarCloud.
* Removed Codecov from the project.

## v. [2.1.1] - 17.12.2023

* Upgrade project dependencies.

## v. [2.1.0] - 08.09.2023

* Added image preview to admin panels.
* Added filters to all endpoints.
* Added `django-filter-stubs` to project dependencies.
* Added `status_full_name` to return game list status as human readable string.

## v. [2.0.1] - 24.08.2023

* Update project dependencies.
* Add stubs for `py`.

## v. [2.0.0] - 14.07.2023

* Changed the username field from `username` to `email`.

## v. [1.1.4] - 29.06.2023

* Added `mypy`.

## v. [1.1.3] - 26.06.2023

* Activate more ruff rules.
* `.gitattributes` file added.

## v. [1.1.2] - 23.06.2023

* Resolve warnings from SonarLint.
* Upgraded the dependencies.
* Added tests for the application logic.
* Added `if TYPE_CHECKING` code block to be ignored by coverage.
* Added helper functions to Makefile for starting the database for development and testing.
* Configure application docker image to run as a non-root user.
* Fixed error with type hinting in the manager for the `Friendship`.
* Added `pytest-xdist` to run tests in parallel.
* Added `pytest-sugar` to improve the tests output.

## v. [1.1.1] - 05.06.2023

* Added configuration for SonarCloud analysis tool.

## v. [1.1.0] - 19.05.2023

* Corrected the Dockerfiles to be compatible with hadolint validation.
* Added `LABEL` to Dockerfiles to automatically link an image to a GitHub repository.
* Added Grafana configuration.
* Added Loki configuration.
* Added Prometheus configuration.
* Added Promtail configuration.
* Created the logging configuration for the application.
* Added custom prometheus metrics for cpu and memory usage.
* Added new decorators for metrics usage.
* Added new dependencies:
  * docker
  * django_prometheus
  * prometheus-client
  * psutil
* Improved scripts (limitation of running shell commands.)

## v. [1.0.3] - 19.04.2023

* Changed the linter to `ruff`.

## v. [1.0.2] - 14.04.2023

* Added configuration for `pre-commit`.
* Added custom pre-push hook for checking if application version and changelog are updated.
* Updated dependencies in requirements.
* Added information in the `README.md` file about installing the `pre-commit` hooks and how to skip the hooks run if needed.
* Added `pre-commit` badge to `README.md` file.

## v. [1.0.1] - 03.04.2023

* Added missing `gettext_lazy` marks.

## v. [1.0.0] - 02.04.2023

* Changed the line length in the project to `120`.
* Added endpoints for the friendship and friendship requests management.
* Changed the name of the field in models from `creation_time` to `created_at` and also `last_modified` to `last_modified_at`.
* Changed the endpoints names to better distinguish between module and endpoints names.
* Added `GameCreateSerializer`.
* Added `ConflictException`.
* Renamed `CreateUserSerializer` to `UserCreateSerializer` and `ListUserSerializer` to `UserSerializer`.

## v. [0.1.0] - 03.08.2022

* Initialization of the project with basic configuration.
