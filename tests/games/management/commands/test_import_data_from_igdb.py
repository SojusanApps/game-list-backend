"""Tests for the `import_data_from_igdb` management command."""

from datetime import UTC, datetime
from io import StringIO
from typing import Any, cast
from unittest.mock import ANY, MagicMock, patch

import pytest
from django.core.management import CommandError, call_command
from model_bakery import baker

from game_list.games.management.commands._igdb_wrapper import (
    BaseIGDBResponse,
    IGDBCompanyResponse,
    IGDBEndpoints,
    IGDBExternalGameResponse,
    IGDBExternalGameSourceResponse,
    IGDBGameEngineResponse,
    IGDBGameModeResponse,
    IGDBGameResponse,
    IGDBGameStatusResponse,
    IGDBGameTypeResponse,
    IGDBGenreResponse,
    IGDBImageResponse,
    IGDBInteractionError,
    IGDBInvolvedCompanyResponse,
    IGDBPlatformResponse,
    IGDBPlayerPerspectiveResponse,
    IGDBWrapper,
)
from game_list.games.management.commands.import_data_from_igdb import Command, RecursiveDataCollector
from game_list.games.models import (
    Company,
    ExternalGame,
    ExternalGameSource,
    Game,
    GameEngine,
    GameMode,
    GameStatus,
    GameType,
    Genre,
    Platform,
    PlayerPerspective,
)


def _game(
    igdb_id: int,
    *,
    name: str = "Test Game",
    slug: str = "test-game",
    **kwargs: Any,  # noqa: ANN401
) -> IGDBGameResponse:
    """Build an `IGDBGameResponse` with sane defaults, overridable via kwargs."""
    kwargs.setdefault("updated_at", 1_700_000_000)
    return IGDBGameResponse(id=igdb_id, name=name, slug=slug, **kwargs)


def _company_response(
    igdb_id: int,
    *,
    name: str = "CD Projekt",
    slug: str = "cd-projekt",
    logo: IGDBImageResponse | None = None,
    updated_at: int = 1_700_000_000,
) -> IGDBCompanyResponse:
    """Build an `IGDBCompanyResponse` with sane defaults, overridable via kwargs."""
    return IGDBCompanyResponse(id=igdb_id, updated_at=updated_at, name=name, slug=slug, logo=logo)


@pytest.fixture
def command_fixture() -> Command:
    """A `Command` instance with IGDB authentication mocked out to avoid real network calls."""
    with patch.object(IGDBWrapper, "get_igdb_access_token", return_value="test-token"):
        return Command()


def _mock_batches(command: Command, batches: list[list[Any]]) -> MagicMock:
    """Patch `command.igdb_wrapper.iter_all_objects` to yield the given batches instead of hitting the network."""
    mock = MagicMock(return_value=iter(batches))
    command.igdb_wrapper.iter_all_objects = mock  # type: ignore[method-assign]
    return mock


# --- add_arguments / handle -------------------------------------------------------------------


@pytest.mark.django_db()
def test_handle_rejects_invalid_what_to_import_choice() -> None:
    """An unknown `what_to_import` value is rejected by argparse `choices` before the command runs."""
    with (
        patch.object(IGDBWrapper, "get_igdb_access_token", return_value="test-token"),
        pytest.raises(CommandError),
    ):
        call_command("import_data_from_igdb", "not_a_real_choice")


@pytest.mark.django_db()
def test_handle_dispatches_single_import_type_with_import_all_false_by_default() -> None:
    """`handle` calls the matching `import_X` method with `import_all=False` when `--all` is not passed."""
    with (
        patch.object(IGDBWrapper, "get_igdb_access_token", return_value="test-token"),
        patch.object(Command, "import_platforms") as mock_import,
        patch("game_list.games.management.commands.import_data_from_igdb.time.sleep"),
    ):
        call_command("import_data_from_igdb", "platforms")
    mock_import.assert_called_once_with(import_all=False, import_start_timestamp=ANY)


@pytest.mark.django_db()
def test_handle_passes_import_all_true_when_all_flag_is_set() -> None:
    """The `--all` flag is forwarded as `import_all=True` to the dispatched import method."""
    with (
        patch.object(IGDBWrapper, "get_igdb_access_token", return_value="test-token"),
        patch.object(Command, "import_genres") as mock_import,
        patch("game_list.games.management.commands.import_data_from_igdb.time.sleep"),
    ):
        call_command("import_data_from_igdb", "genres", "--all")
    mock_import.assert_called_once_with(import_all=True, import_start_timestamp=ANY)


@pytest.mark.django_db()
def test_handle_dispatches_multiple_import_types_in_order() -> None:
    """Multiple `what_to_import` values each dispatch to their own `import_X` method."""
    with (
        patch.object(IGDBWrapper, "get_igdb_access_token", return_value="test-token"),
        patch.object(Command, "import_platforms") as mock_platforms,
        patch.object(Command, "import_genres") as mock_genres,
        patch("game_list.games.management.commands.import_data_from_igdb.time.sleep"),
    ):
        call_command("import_data_from_igdb", "platforms", "genres")
    mock_platforms.assert_called_once()
    mock_genres.assert_called_once()


@pytest.mark.django_db()
def test_handle_catches_exception_from_one_import_and_continues_with_the_next() -> None:
    """An exception raised by one import action is caught and logged, and later actions still run."""
    out = StringIO()
    with (
        patch.object(IGDBWrapper, "get_igdb_access_token", return_value="test-token"),
        patch.object(Command, "import_platforms", side_effect=RuntimeError("boom")),
        patch.object(Command, "import_genres") as mock_genres,
        patch("game_list.games.management.commands.import_data_from_igdb.time.sleep"),
    ):
        call_command("import_data_from_igdb", "platforms", "genres", stdout=out)
    mock_genres.assert_called_once()
    assert "Error importing platforms: boom" in out.getvalue()
    assert "Import process completed." in out.getvalue()


# --- _get_company ------------------------------------------------------------------------------


def test_get_company_returns_none_when_involved_companies_is_none() -> None:
    """`_get_company` returns `None` when there is no involved-companies list at all."""
    result = Command._get_company(  # noqa: SLF001
        company_type="developer",
        involved_companies=None,
        company_igdb_to_db_mapping={},
    )
    assert result is None


def test_get_company_returns_mapped_developer() -> None:
    """`_get_company` returns the mapped `Company` for the involved company flagged as developer."""
    developer = Company(igdb_id=1)
    involved = [
        IGDBInvolvedCompanyResponse(id=1, company=1, developer=True, publisher=False),
        IGDBInvolvedCompanyResponse(id=2, company=2, developer=False, publisher=True),
    ]
    result = Command._get_company(  # noqa: SLF001
        company_type="developer",
        involved_companies=involved,
        company_igdb_to_db_mapping={1: developer},
    )
    assert result is developer


def test_get_company_returns_mapped_publisher() -> None:
    """`_get_company` returns the mapped `Company` for the involved company flagged as publisher."""
    publisher = Company(igdb_id=2)
    involved = [
        IGDBInvolvedCompanyResponse(id=1, company=1, developer=True, publisher=False),
        IGDBInvolvedCompanyResponse(id=2, company=2, developer=False, publisher=True),
    ]
    result = Command._get_company(  # noqa: SLF001
        company_type="publisher",
        involved_companies=involved,
        company_igdb_to_db_mapping={2: publisher},
    )
    assert result is publisher


def test_get_company_returns_none_when_no_company_has_the_requested_flag() -> None:
    """`_get_company` returns `None` when no involved company matches the requested type."""
    involved = [IGDBInvolvedCompanyResponse(id=1, company=1, developer=False, publisher=False)]
    result = Command._get_company(  # noqa: SLF001
        company_type="developer",
        involved_companies=involved,
        company_igdb_to_db_mapping={1: Company(igdb_id=1)},
    )
    assert result is None


def test_get_company_returns_none_when_matched_company_not_in_mapping() -> None:
    """`_get_company` returns `None` when the matched IGDB company has no local `Company` counterpart."""
    involved = [IGDBInvolvedCompanyResponse(id=1, company=1, developer=True, publisher=False)]
    result = Command._get_company(  # noqa: SLF001
        company_type="developer",
        involved_companies=involved,
        company_igdb_to_db_mapping={},
    )
    assert result is None


# --- _get_game_input -----------------------------------------------------------------------------


def test_get_game_input_maps_full_game(command_fixture: Command) -> None:
    """`_get_game_input` maps all IGDB game fields, including nested cover/screenshots/companies.

    `involved_companies`/`screenshots` are passed as raw dicts (not pre-built dataclasses) because
    `IGDBGameResponse.__post_init__` only converts nested dicts into their dataclass form - it filters
    out (drops) any entry that is already a dataclass instance, mirroring what the real IGDB JSON payload
    looks like before `IGDBWrapper` casts it.
    """
    developer = Company(igdb_id=1)
    publisher = Company(igdb_id=2)
    involved = [
        {"id": 1, "company": 1, "developer": True, "publisher": False},
        {"id": 2, "company": 2, "developer": False, "publisher": True},
    ]
    item = _game(
        1,
        name="Cyberpunk 2077",
        slug="cyberpunk-2077",
        cover=IGDBImageResponse(id=1, image_id="cover123"),
        first_release_date=1_600_000_000,
        summary="A game.",
        involved_companies=involved,
        game_type=10,
        game_status=20,
        screenshots=[{"id": 1, "image_id": "shot1"}, {"id": 2, "image_id": "shot2"}],
    )
    result = command_fixture._get_game_input(  # noqa: SLF001
        item,
        company_igdb_to_db_mapping={1: developer, 2: publisher},
        extra_mappings={"game_type": {10: "GT"}, "game_status": {20: "GS"}},
    )
    assert result["title_en"] == "Cyberpunk 2077"
    assert result["slug"] == "cyberpunk-2077"
    assert result["release_date"] == datetime.fromtimestamp(1_600_000_000, tz=UTC).date()
    assert result["cover_image_id"] == "cover123"
    assert result["summary_en"] == "A game."
    assert result["developer"] is developer
    assert result["publisher"] is publisher
    assert result["game_type"] == "GT"
    assert result["game_status"] == "GS"
    assert result["screenshots"] == ["shot1", "shot2"]


def test_get_game_input_handles_missing_optional_fields(command_fixture: Command) -> None:
    """`_get_game_input` falls back to empty/None defaults when optional IGDB fields are absent."""
    item = _game(1, cover=None, first_release_date=None, screenshots=None, involved_companies=None)
    result = command_fixture._get_game_input(item, company_igdb_to_db_mapping={}, extra_mappings=None)  # noqa: SLF001
    assert result["release_date"] is None
    assert result["cover_image_id"] == ""
    assert result["developer"] is None
    assert result["publisher"] is None
    assert result["game_type"] is None
    assert result["game_status"] is None
    assert result["screenshots"] == []


def test_get_game_input_ignores_game_type_when_not_in_mapping(command_fixture: Command) -> None:
    """`_get_game_input` leaves `game_type`/`game_status` as `None` when the IGDB id is missing from the mapping."""
    item = _game(1, game_type=99, game_status=98)
    result = command_fixture._get_game_input(  # noqa: SLF001
        item,
        company_igdb_to_db_mapping={},
        extra_mappings={"game_type": {}, "game_status": {}},
    )
    assert result["game_type"] is None
    assert result["game_status"] is None


# --- simple _get_X_input mappers -------------------------------------------------------------


def test_get_game_type_input(command_fixture: Command) -> None:
    """`_get_game_type_input` maps the IGDB `type` field onto the concrete `type_en` column."""
    item = IGDBGameTypeResponse(id=1, updated_at=1, type="Main Game")
    assert command_fixture._get_game_type_input(item) == {"type_en": "Main Game"}  # noqa: SLF001


def test_get_game_status_input(command_fixture: Command) -> None:
    """`_get_game_status_input` maps the IGDB `status` field onto the concrete `status_en` column."""
    item = IGDBGameStatusResponse(id=1, updated_at=1, status="Released")
    assert command_fixture._get_game_status_input(item) == {"status_en": "Released"}  # noqa: SLF001


def test_get_platform_input(command_fixture: Command) -> None:
    """`_get_platform_input` maps the IGDB `abbreviation`/`name` fields onto the concrete `name_en` column."""
    item = IGDBPlatformResponse(id=1, updated_at=1, name="PlayStation 5", abbreviation="PS5")
    assert command_fixture._get_platform_input(item) == {  # noqa: SLF001
        "abbreviation": "PS5",
        "name_en": "PlayStation 5",
    }


def test_get_company_input_with_logo(command_fixture: Command) -> None:
    """`_get_company_input` maps the IGDB `name`/`slug`/logo image id onto the concrete `name_en` column."""
    item = _company_response(1, logo=IGDBImageResponse(id=1, image_id="logo123"))
    assert command_fixture._get_company_input(item) == {  # noqa: SLF001
        "name_en": "CD Projekt",
        "slug": "cd-projekt",
        "company_logo_id": "logo123",
    }


def test_get_company_input_without_logo(command_fixture: Command) -> None:
    """`_get_company_input` defaults the logo id to an empty string when there is no logo."""
    item = _company_response(1, logo=None)
    assert command_fixture._get_company_input(item)["company_logo_id"] == ""  # noqa: SLF001


# --- _get_model_input ----------------------------------------------------------------------------


def test_get_model_input_for_game(command_fixture: Command) -> None:
    """`_get_model_input` builds the base igdb_id/igdb_updated_at fields plus the Game-specific fields."""
    item = _game(1, updated_at=1_700_000_000)
    result = command_fixture._get_model_input(item, company_igdb_to_db_mapping={})  # noqa: SLF001
    assert result["igdb_id"] == 1
    assert result["igdb_updated_at"] == datetime.fromtimestamp(1_700_000_000, tz=UTC)
    assert result["title_en"] == "Test Game"


def test_get_model_input_with_falsy_updated_at_yields_none(command_fixture: Command) -> None:
    """`_get_model_input` maps a falsy `updated_at` (e.g. `0`) to `None` instead of the epoch."""
    item = _game(1, updated_at=0)
    result = command_fixture._get_model_input(item, company_igdb_to_db_mapping={})  # noqa: SLF001
    assert result["igdb_updated_at"] is None


@pytest.mark.parametrize(
    "response",
    [
        IGDBGenreResponse(id=1, updated_at=1, name="Action"),
        IGDBGameModeResponse(id=1, updated_at=1, name="Co-op"),
        IGDBPlayerPerspectiveResponse(id=1, updated_at=1, name="First person"),
        IGDBGameEngineResponse(id=1, updated_at=1, name="Unreal Engine"),
        IGDBExternalGameSourceResponse(id=1, updated_at=1, name="Steam"),
    ],
)
def test_get_model_input_for_simple_named_types(command_fixture: Command, response: BaseIGDBResponse) -> None:
    """`_get_model_input` maps `name` onto `name_en` for the family of simple named response types."""
    result = command_fixture._get_model_input(  # noqa: SLF001
        response,  # type: ignore[arg-type]
        company_igdb_to_db_mapping={},
    )
    assert result["name_en"] == response.name  # type: ignore[attr-defined]


def test_get_model_input_for_external_game_with_source_mapping(command_fixture: Command) -> None:
    """`_get_model_input` resolves `external_game_source` through the extra mapping into a local pk."""
    item = IGDBExternalGameResponse(id=1, updated_at=1, uid="730", external_game_source=99, url="https://x")
    result = command_fixture._get_model_input(  # noqa: SLF001
        item,
        company_igdb_to_db_mapping={},
        extra_mappings={"external_game_sources": {99: 5}},
    )
    assert result["external_id"] == "730"
    assert result["url"] == "https://x"
    assert result["external_game_source_id"] == 5  # noqa: PLR2004


def test_get_model_input_for_external_game_without_mapping(command_fixture: Command) -> None:
    """`_get_model_input` leaves `external_game_source_id` as `None` when no extra mapping is supplied."""
    item = IGDBExternalGameResponse(id=1, updated_at=1, uid="730", external_game_source=99)
    result = command_fixture._get_model_input(item, company_igdb_to_db_mapping={})  # noqa: SLF001
    assert result["external_game_source_id"] is None


def test_get_model_input_for_game_type(command_fixture: Command) -> None:
    """`_get_model_input` maps `type` onto `type_en` for `IGDBGameTypeResponse`."""
    item = IGDBGameTypeResponse(id=1, updated_at=1, type="DLC")
    result = command_fixture._get_model_input(item, company_igdb_to_db_mapping={})  # noqa: SLF001
    assert result["type_en"] == "DLC"


def test_get_model_input_for_game_status(command_fixture: Command) -> None:
    """`_get_model_input` maps `status` onto `status_en` for `IGDBGameStatusResponse`."""
    item = IGDBGameStatusResponse(id=1, updated_at=1, status="Alpha")
    result = command_fixture._get_model_input(item, company_igdb_to_db_mapping={})  # noqa: SLF001
    assert result["status_en"] == "Alpha"


def test_get_model_input_for_platform(command_fixture: Command) -> None:
    """`_get_model_input` maps `abbreviation`/`name` (onto `name_en`) for `IGDBPlatformResponse`."""
    item = IGDBPlatformResponse(id=1, updated_at=1, name="PC", abbreviation="PC")
    result = command_fixture._get_model_input(item, company_igdb_to_db_mapping={})  # noqa: SLF001
    assert result["name_en"] == "PC"
    assert result["abbreviation"] == "PC"


def test_get_model_input_for_company(command_fixture: Command) -> None:
    """`_get_model_input` maps `name`(onto `name_en`)/`slug`/logo for `IGDBCompanyResponse`."""
    item = _company_response(1)
    result = command_fixture._get_model_input(item, company_igdb_to_db_mapping={})  # noqa: SLF001
    assert result["name_en"] == "CD Projekt"
    assert result["slug"] == "cd-projekt"


def test_get_model_input_raises_for_unsupported_type(command_fixture: Command) -> None:
    """`_get_model_input` raises `IGDBInteractionError` for a response type not handled by the `match`."""
    unsupported = BaseIGDBResponse(id=1, updated_at=1)
    with pytest.raises(IGDBInteractionError):
        command_fixture._get_model_input(  # noqa: SLF001
            unsupported,  # type: ignore[arg-type]
            company_igdb_to_db_mapping={},
        )


# --- _build_query --------------------------------------------------------------------------------


@pytest.mark.django_db()
def test_build_query_unchanged_when_no_existing_rows(command_fixture: Command) -> None:
    """`_build_query` leaves the query untouched when the target model has no rows yet."""
    query = command_fixture._build_query(  # noqa: SLF001
        "fields name, updated_at;",
        Genre,
        import_all=False,
        import_start_timestamp=None,
    )
    assert query == "fields name, updated_at;"


@pytest.mark.django_db()
def test_build_query_adds_last_updated_clause_when_row_exists_and_not_import_all(command_fixture: Command) -> None:
    """`_build_query` adds an `updated_at >` clause scoped to the max `igdb_updated_at` already stored."""
    baker.make(Genre, igdb_updated_at=datetime(2024, 1, 1, tzinfo=UTC))
    query = command_fixture._build_query(  # noqa: SLF001
        "fields name, updated_at;",
        Genre,
        import_all=False,
        import_start_timestamp=None,
    )
    expected_ts = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp())
    assert query == f"fields name, updated_at; where updated_at > {expected_ts};"


@pytest.mark.django_db()
def test_build_query_ignores_last_updated_clause_when_import_all(command_fixture: Command) -> None:
    """`_build_query` skips the last-updated clause entirely when `import_all=True`."""
    baker.make(Genre, igdb_updated_at=datetime(2024, 1, 1, tzinfo=UTC))
    query = command_fixture._build_query(  # noqa: SLF001
        "fields name, updated_at;",
        Genre,
        import_all=True,
        import_start_timestamp=None,
    )
    assert query == "fields name, updated_at;"


@pytest.mark.django_db()
def test_build_query_adds_start_timestamp_clause(command_fixture: Command) -> None:
    """`_build_query` adds an `updated_at <=` clause bounding the import to `import_start_timestamp`."""
    query = command_fixture._build_query(  # noqa: SLF001
        "fields name, updated_at;",
        Genre,
        import_all=False,
        import_start_timestamp=1_700_000_000,
    )
    assert query == "fields name, updated_at; where updated_at <= 1700000000;"


@pytest.mark.django_db()
def test_build_query_combines_both_clauses(command_fixture: Command) -> None:
    """`_build_query` joins the last-updated and start-timestamp clauses with `&` when both apply."""
    baker.make(Genre, igdb_updated_at=datetime(2024, 1, 1, tzinfo=UTC))
    query = command_fixture._build_query(  # noqa: SLF001
        "fields name, updated_at;",
        Genre,
        import_all=False,
        import_start_timestamp=1_700_000_000,
    )
    expected_ts = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp())
    assert query == f"fields name, updated_at; where updated_at > {expected_ts} & updated_at <= 1700000000;"


# --- _get_company_mapping --------------------------------------------------------------------------


@pytest.mark.django_db()
def test_get_company_mapping_returns_known_companies_only(command_fixture: Command) -> None:
    """`_get_company_mapping` returns only companies that exist locally, keyed by IGDB id."""
    known = baker.make(Company, igdb_id=101)
    involved = [{"id": 1, "company": 101, "developer": True, "publisher": False}]
    game = _game(1, involved_companies=involved)
    unknown_game = _game(
        2,
        involved_companies=[{"id": 2, "company": 999, "developer": True, "publisher": False}],
    )
    mapping = command_fixture._get_company_mapping([game, unknown_game])  # noqa: SLF001
    assert mapping == {101: known}


@pytest.mark.django_db()
def test_get_company_mapping_ignores_non_game_items(command_fixture: Command) -> None:
    """`_get_company_mapping` ignores items that are not `IGDBGameResponse` (e.g. genres)."""
    genre = IGDBGenreResponse(id=1, updated_at=1, name="Action")
    mapping = command_fixture._get_company_mapping([genre])  # noqa: SLF001
    assert mapping == {}


@pytest.mark.django_db()
def test_get_company_mapping_empty_when_no_involved_companies(command_fixture: Command) -> None:
    """`_get_company_mapping` returns an empty dict when no game has involved companies."""
    game = _game(1, involved_companies=None)
    mapping = command_fixture._get_company_mapping([game])  # noqa: SLF001
    assert mapping == {}


# --- _import_data ------------------------------------------------------------------------------


@pytest.mark.django_db()
def test_import_data_creates_new_rows_on_first_import(command_fixture: Command) -> None:
    """`_import_data` creates a DB row for each unique item yielded by `iter_all_objects`."""
    genre_1 = IGDBGenreResponse(id=101, updated_at=1_700_000_000, name="Action")
    genre_2 = IGDBGenreResponse(id=102, updated_at=1_700_000_000, name="RPG")
    _mock_batches(command_fixture, [[genre_1, genre_2]])

    results = list(
        command_fixture._import_data(  # noqa: SLF001
            endpoint=IGDBEndpoints.GENRES,
            query="fields name, updated_at;",
            model=Genre,
        ),
    )

    assert len(results) == 1
    created, raw = results[0]
    assert len(created) == 2  # noqa: PLR2004
    assert raw == [genre_1, genre_2]
    assert set(Genre.objects.values_list("igdb_id", flat=True)) == {101, 102}


@pytest.mark.django_db()
def test_import_data_deduplicates_keeping_last_occurrence(command_fixture: Command) -> None:
    """`_import_data` deduplicates items with the same id within a batch, keeping the last occurrence."""
    genre_v1 = IGDBGenreResponse(id=101, updated_at=1_700_000_000, name="First")
    genre_v2 = IGDBGenreResponse(id=101, updated_at=1_700_000_001, name="Second")
    _mock_batches(command_fixture, [[genre_v1, genre_v2]])

    results = list(
        command_fixture._import_data(  # noqa: SLF001
            endpoint=IGDBEndpoints.GENRES,
            query="fields name, updated_at;",
            model=Genre,
        ),
    )

    created, _raw = results[0]
    assert len(created) == 1
    assert Genre.objects.get(igdb_id=101).name_en == "Second"


@pytest.mark.django_db()
def test_import_data_skips_empty_batches(command_fixture: Command) -> None:
    """`_import_data` skips falsy batches (e.g. empty lists) without yielding for them."""
    genre = IGDBGenreResponse(id=101, updated_at=1_700_000_000, name="Action")
    _mock_batches(command_fixture, [[], [genre]])

    results = list(
        command_fixture._import_data(  # noqa: SLF001
            endpoint=IGDBEndpoints.GENRES,
            query="fields name, updated_at;",
            model=Genre,
        ),
    )

    assert len(results) == 1


@pytest.mark.django_db()
def test_import_data_updates_existing_row_via_bulk_create_conflicts(command_fixture: Command) -> None:
    """`_import_data` updates an existing row on conflict, and scopes the query to the last known update.

    Uses `Platform.abbreviation` (a plain, non-translated field) to verify the update mechanism itself.
    See `test_import_data_incremental_update_updates_translated_name_field` below for the translated-field
    case (`Genre.name`, `Game.title`, etc.), which goes through the `_en`-suffixed concrete column instead.
    """
    baker.make(Platform, igdb_id=101, abbreviation="OLD", igdb_updated_at=datetime(2024, 1, 1, tzinfo=UTC))
    updated_platform = IGDBPlatformResponse(id=101, updated_at=1_700_000_000, name="PC", abbreviation="NEW")
    mock_iter = _mock_batches(command_fixture, [[updated_platform]])

    list(
        command_fixture._import_data(  # noqa: SLF001
            endpoint=IGDBEndpoints.PLATFORMS,
            query="fields abbreviation, name, updated_at;",
            model=Platform,
        ),
    )

    assert Platform.objects.count() == 1
    assert Platform.objects.get(igdb_id=101).abbreviation == "NEW"
    call_kwargs = mock_iter.call_args.kwargs
    assert "updated_at > " in call_kwargs["query"]


@pytest.mark.django_db()
def test_import_data_incremental_update_updates_translated_name_field(command_fixture: Command) -> None:
    """On conflict, translated fields are updated via their concrete `_en` column.

    `_get_model_input` builds `model_input`/`update_fields` using the `_en`-suffixed concrete column
    (e.g. `"name_en"`) rather than the modeltranslation proxy key (`"name"`), since `Genre.name` is a
    descriptor backed by `name_en`/`name_pl` and Postgres has no real `name` column for `bulk_create`'s
    `ON CONFLICT DO UPDATE` to target. Using `name_en` directly ensures re-importing an already-known
    row actually refreshes the value application code reads.
    """
    baker.make(Genre, igdb_id=101, name_en="Old Name", igdb_updated_at=datetime(2024, 1, 1, tzinfo=UTC))
    updated_genre = IGDBGenreResponse(id=101, updated_at=1_700_000_000, name="New Name")
    _mock_batches(command_fixture, [[updated_genre]])

    list(
        command_fixture._import_data(  # noqa: SLF001
            endpoint=IGDBEndpoints.GENRES,
            query="fields name, updated_at;",
            model=Genre,
        ),
    )

    assert Genre.objects.get(igdb_id=101).name_en == "New Name"


@pytest.mark.django_db()
def test_import_data_import_all_bypasses_last_updated_scoping(command_fixture: Command) -> None:
    """`_import_data` omits the last-updated clause from the query when `import_all=True`."""
    baker.make(Genre, igdb_id=101, name_en="Old Name", igdb_updated_at=datetime(2024, 1, 1, tzinfo=UTC))
    updated_genre = IGDBGenreResponse(id=101, updated_at=1_700_000_000, name="New Name")
    mock_iter = _mock_batches(command_fixture, [[updated_genre]])

    list(
        command_fixture._import_data(  # noqa: SLF001
            endpoint=IGDBEndpoints.GENRES,
            query="fields name, updated_at;",
            model=Genre,
            import_all=True,
        ),
    )

    call_kwargs = mock_iter.call_args.kwargs
    assert "updated_at >" not in call_kwargs["query"]


@pytest.mark.django_db()
def test_import_data_computes_search_title_for_game_model(command_fixture: Command) -> None:
    """`_import_data` computes and stores `search_title` for `Game` rows, since `bulk_create` skips `save()`."""
    game_resp = _game(201, name="The Witcher 3", slug="witcher-3")
    _mock_batches(command_fixture, [[game_resp]])

    list(
        command_fixture._import_data(  # noqa: SLF001
            endpoint=IGDBEndpoints.GAMES,
            query="fields name, slug, updated_at;",
            model=Game,
        ),
    )

    assert Game.objects.get(igdb_id=201).search_title == "the witcher 3"


@pytest.mark.django_db()
def test_import_data_maps_companies_for_game_model(command_fixture: Command) -> None:
    """`_import_data` resolves `developer`/`publisher` for `Game` rows via `_get_company_mapping`."""
    dev_company = baker.make(Company, igdb_id=501)
    involved = [{"id": 1, "company": 501, "developer": True, "publisher": False}]
    game_resp = _game(202, name="Cyberpunk", slug="cyberpunk", involved_companies=involved)
    _mock_batches(command_fixture, [[game_resp]])

    list(
        command_fixture._import_data(  # noqa: SLF001
            endpoint=IGDBEndpoints.GAMES,
            query="fields name, slug, updated_at;",
            model=Game,
        ),
    )

    game = Game.objects.get(igdb_id=202)
    assert game.developer_id == dev_company.id


# --- import_games (batching + relations) ---------------------------------------------------------


@pytest.mark.django_db()
def test_import_games_creates_games_with_simple_and_recursive_relations(command_fixture: Command) -> None:
    """`import_games` links simple relations per-batch and recursive (self-referential) relations at the end."""
    genre = baker.make(Genre, igdb_id=10)
    platform = baker.make(Platform, igdb_id=20)
    mode = baker.make(GameMode, igdb_id=30)
    perspective = baker.make(PlayerPerspective, igdb_id=40)
    engine = baker.make(GameEngine, igdb_id=50)
    ext_source = baker.make(ExternalGameSource, igdb_id=60)
    ext_game = baker.make(ExternalGame, igdb_id=70, external_game_source=ext_source)
    game_type = baker.make(GameType, igdb_id=80)
    game_status = baker.make(GameStatus, igdb_id=90)

    base_game = _game(
        1000,
        name="Base Game",
        slug="base-game",
        genres=[10],
        platforms=[20],
        game_modes=[30],
        player_perspectives=[40],
        game_engines=[50],
        external_games=[70],
        game_type=80,
        game_status=90,
    )
    dlc_game = _game(1001, name="DLC Game", slug="dlc-game", parent_game=1000, dlcs=[1000])

    _mock_batches(command_fixture, [[base_game], [dlc_game]])

    command_fixture.import_games()

    base = Game.objects.get(igdb_id=1000)
    dlc = Game.objects.get(igdb_id=1001)

    assert list(base.genres.values_list("igdb_id", flat=True)) == [genre.igdb_id]
    assert list(base.platforms.values_list("igdb_id", flat=True)) == [platform.igdb_id]
    assert list(base.game_modes.values_list("igdb_id", flat=True)) == [mode.igdb_id]
    assert list(base.player_perspectives.values_list("igdb_id", flat=True)) == [perspective.igdb_id]
    assert list(base.game_engines.values_list("igdb_id", flat=True)) == [engine.igdb_id]
    assert list(base.external_games.values_list("igdb_id", flat=True)) == [ext_game.igdb_id]
    assert base.game_type_id == game_type.id
    assert base.game_status_id == game_status.id

    assert dlc.parent_game_id == base.id
    assert list(dlc.dlcs.values_list("igdb_id", flat=True)) == [base.igdb_id]


@pytest.mark.django_db()
def test_import_games_skips_relations_for_unknown_igdb_ids(command_fixture: Command) -> None:
    """`import_games` silently skips relation targets whose IGDB id is not present locally."""
    game_resp = _game(2000, name="Solo Game", slug="solo-game", genres=[999], parent_game=888)
    _mock_batches(command_fixture, [[game_resp]])

    command_fixture.import_games()

    game = Game.objects.get(igdb_id=2000)
    assert game.genres.count() == 0
    assert game.parent_game_id is None


# --- _process_game_batch / _collect_simple_relations / _collect_recursive_relations ---------------


@pytest.mark.django_db()
def test_process_game_batch_skips_non_game_response_items(command_fixture: Command) -> None:
    """`_process_game_batch` defensively skips any zipped item that isn't an `IGDBGameResponse`.

    In practice `igdb_games` always comes from a single, homogeneous IGDB endpoint response, so this
    branch is not reachable through the public `import_games` path - it is exercised directly here.
    """
    game = baker.make(Game)
    collector = RecursiveDataCollector(parent_updates=[], recursive_m2m_data={}, all_target_igdb_ids=set())
    mappings: dict[str, dict[int, int]] = {
        "genres": {},
        "platforms": {},
        "game_modes": {},
        "player_perspectives": {},
        "game_engines": {},
        "external_games": {},
    }

    command_fixture._process_game_batch(  # noqa: SLF001
        [game],
        [None],  # type: ignore[list-item]
        mappings,
        collector,
    )

    assert collector.parent_updates == []
    assert collector.all_target_igdb_ids == set()


@pytest.mark.django_db()
def test_collect_simple_relations_skips_unmapped_ids(command_fixture: Command) -> None:
    """`_collect_simple_relations` only builds through-rows for ids present in the igdb-to-db mapping."""
    genre = baker.make(Genre, igdb_id=10)
    game = baker.make(Game)
    game_from_igdb = _game(1, genres=[10, 999])
    mappings: dict[str, dict[int, int]] = {
        "genres": {10: genre.id},
        "platforms": {},
        "game_modes": {},
        "player_perspectives": {},
        "game_engines": {},
        "external_games": {},
    }
    rel_containers: dict[str, list[Any]] = {
        "genres": [],
        "platforms": [],
        "modes": [],
        "perspectives": [],
        "engines": [],
        "external_games": [],
    }

    command_fixture._collect_simple_relations(game, game_from_igdb, mappings, rel_containers)  # noqa: SLF001

    assert len(rel_containers["genres"]) == 1
    assert rel_containers["genres"][0].genre_id == genre.id


@pytest.mark.django_db()
def test_collect_simple_relations_no_op_when_game_has_no_relations(command_fixture: Command) -> None:
    """`_collect_simple_relations` leaves every relation bucket empty when the IGDB game has none set."""
    game = baker.make(Game)
    game_from_igdb = _game(1)
    mappings: dict[str, dict[int, int]] = {
        "genres": {},
        "platforms": {},
        "game_modes": {},
        "player_perspectives": {},
        "game_engines": {},
        "external_games": {},
    }
    rel_containers: dict[str, list[Any]] = {
        "genres": [],
        "platforms": [],
        "modes": [],
        "perspectives": [],
        "engines": [],
        "external_games": [],
    }

    command_fixture._collect_simple_relations(game, game_from_igdb, mappings, rel_containers)  # noqa: SLF001

    assert all(not bucket for bucket in rel_containers.values())


@pytest.mark.django_db()
def test_collect_recursive_relations_populates_collector(command_fixture: Command) -> None:
    """`_collect_recursive_relations` records the parent link and each recursive m2m target."""
    game = baker.make(Game)
    collector = RecursiveDataCollector(
        parent_updates=[],
        recursive_m2m_data={"bundles": [], "dlcs": []},
        all_target_igdb_ids=set(),
    )
    game_from_igdb = _game(1, parent_game=99, bundles=[100, 101])

    command_fixture._collect_recursive_relations(game, game_from_igdb, collector)  # noqa: SLF001

    assert collector.parent_updates == [(game.id, 99)]
    assert collector.recursive_m2m_data["bundles"] == [(game.id, 100), (game.id, 101)]
    assert collector.recursive_m2m_data["dlcs"] == []
    assert collector.all_target_igdb_ids == {99, 100, 101}


@pytest.mark.django_db()
def test_collect_recursive_relations_no_op_without_parent_or_targets(command_fixture: Command) -> None:
    """`_collect_recursive_relations` leaves the collector untouched when there is no parent or m2m target."""
    game = baker.make(Game)
    collector = RecursiveDataCollector(
        parent_updates=[],
        recursive_m2m_data={"bundles": []},
        all_target_igdb_ids=set(),
    )
    game_from_igdb = _game(1)

    command_fixture._collect_recursive_relations(game, game_from_igdb, collector)  # noqa: SLF001

    assert collector.parent_updates == []
    assert collector.recursive_m2m_data["bundles"] == []
    assert collector.all_target_igdb_ids == set()


# --- _bulk_create_simple_relations ----------------------------------------------------------------


@pytest.mark.django_db()
def test_bulk_create_simple_relations_persists_and_ignores_conflicts(command_fixture: Command) -> None:
    """`_bulk_create_simple_relations` persists relation rows and ignores duplicate conflicts."""
    game = baker.make(Game)
    genre = baker.make(Genre)
    through_model = cast("type[Any]", Game.genres.through)
    relation = through_model(game_id=game.id, genre_id=genre.id)
    rel_containers: dict[str, list[Any]] = {
        "genres": [relation, relation],
        "platforms": [],
        "modes": [],
        "perspectives": [],
        "engines": [],
        "external_games": [],
    }

    command_fixture._bulk_create_simple_relations(rel_containers)  # noqa: SLF001

    assert list(game.genres.values_list("id", flat=True)) == [genre.id]


# --- _handle_recursive_relations -------------------------------------------------------------------


@pytest.mark.django_db()
def test_handle_recursive_relations_returns_early_when_no_target_ids(command_fixture: Command) -> None:
    """`_handle_recursive_relations` returns immediately when the collector has no target ids at all."""
    collector = RecursiveDataCollector(parent_updates=[], recursive_m2m_data={}, all_target_igdb_ids=set())

    command_fixture._handle_recursive_relations(collector)  # noqa: SLF001 - should not raise


@pytest.mark.django_db()
def test_handle_recursive_relations_updates_parent_and_skips_missing_targets(command_fixture: Command) -> None:
    """`_handle_recursive_relations` sets `parent_game` and m2m relations, skipping ids missing from the DB."""
    base = baker.make(Game, igdb_id=1000)
    child = baker.make(Game, igdb_id=1001)
    collector = RecursiveDataCollector(
        parent_updates=[(child.id, 1000)],
        recursive_m2m_data={"bundles": [(child.id, 1000), (child.id, 9999)], "dlcs": []},
        all_target_igdb_ids={1000, 9999},
    )

    command_fixture._handle_recursive_relations(collector)  # noqa: SLF001

    child.refresh_from_db()
    assert child.parent_game_id == base.id
    assert list(child.bundles.values_list("igdb_id", flat=True)) == [base.igdb_id]


@pytest.mark.django_db()
def test_handle_recursive_relations_with_only_m2m_no_parent_updates(command_fixture: Command) -> None:
    """`_handle_recursive_relations` handles m2m-only collectors (no `parent_updates` entries)."""
    base = baker.make(Game, igdb_id=2000)
    child = baker.make(Game, igdb_id=2001)
    collector = RecursiveDataCollector(
        parent_updates=[],
        recursive_m2m_data={"dlcs": [(child.id, 2000)], "bundles": []},
        all_target_igdb_ids={2000},
    )

    command_fixture._handle_recursive_relations(collector)  # noqa: SLF001

    assert list(child.dlcs.values_list("igdb_id", flat=True)) == [base.igdb_id]


# --- thin import_X wrapper methods -----------------------------------------------------------------


@pytest.mark.django_db()
def test_import_companies_creates_company(command_fixture: Command) -> None:
    """`import_companies` creates a `Company` row from a canned IGDB companies response."""
    company_resp = _company_response(1, name="CD Projekt")
    _mock_batches(command_fixture, [[company_resp]])

    command_fixture.import_companies()

    assert Company.objects.filter(igdb_id=1, name_en="CD Projekt").exists()


@pytest.mark.django_db()
def test_import_genres_creates_genre(command_fixture: Command) -> None:
    """`import_genres` creates a `Genre` row from a canned IGDB genres response."""
    genre_resp = IGDBGenreResponse(id=1, updated_at=1_700_000_000, name="Action")
    _mock_batches(command_fixture, [[genre_resp]])

    command_fixture.import_genres()

    assert Genre.objects.filter(igdb_id=1, name_en="Action").exists()


@pytest.mark.django_db()
def test_import_platforms_creates_platform(command_fixture: Command) -> None:
    """`import_platforms` creates a `Platform` row from a canned IGDB platforms response."""
    platform_resp = IGDBPlatformResponse(id=1, updated_at=1_700_000_000, name="PlayStation 5", abbreviation="PS5")
    _mock_batches(command_fixture, [[platform_resp]])

    command_fixture.import_platforms()

    assert Platform.objects.filter(igdb_id=1, name_en="PlayStation 5", abbreviation="PS5").exists()


@pytest.mark.django_db()
def test_import_game_modes_creates_game_mode(command_fixture: Command) -> None:
    """`import_game_modes` creates a `GameMode` row from a canned IGDB game-modes response."""
    mode_resp = IGDBGameModeResponse(id=1, updated_at=1_700_000_000, name="Co-op")
    _mock_batches(command_fixture, [[mode_resp]])

    command_fixture.import_game_modes()

    assert GameMode.objects.filter(igdb_id=1, name_en="Co-op").exists()


@pytest.mark.django_db()
def test_import_player_perspectives_creates_player_perspective(command_fixture: Command) -> None:
    """`import_player_perspectives` creates a `PlayerPerspective` row from a canned IGDB response."""
    perspective_resp = IGDBPlayerPerspectiveResponse(id=1, updated_at=1_700_000_000, name="First person")
    _mock_batches(command_fixture, [[perspective_resp]])

    command_fixture.import_player_perspectives()

    assert PlayerPerspective.objects.filter(igdb_id=1, name_en="First person").exists()


@pytest.mark.django_db()
def test_import_game_engines_creates_game_engine(command_fixture: Command) -> None:
    """`import_game_engines` creates a `GameEngine` row from a canned IGDB game-engines response."""
    engine_resp = IGDBGameEngineResponse(id=1, updated_at=1_700_000_000, name="Unreal Engine")
    _mock_batches(command_fixture, [[engine_resp]])

    command_fixture.import_game_engines()

    assert GameEngine.objects.filter(igdb_id=1, name="Unreal Engine").exists()


@pytest.mark.django_db()
def test_import_game_types_creates_game_type(command_fixture: Command) -> None:
    """`import_game_types` creates a `GameType` row from a canned IGDB game-types response."""
    type_resp = IGDBGameTypeResponse(id=1, updated_at=1_700_000_000, type="DLC")
    _mock_batches(command_fixture, [[type_resp]])

    command_fixture.import_game_types()

    assert GameType.objects.filter(igdb_id=1, type="DLC").exists()


@pytest.mark.django_db()
def test_import_game_statuses_creates_game_status(command_fixture: Command) -> None:
    """`import_game_statuses` creates a `GameStatus` row from a canned IGDB game-statuses response."""
    status_resp = IGDBGameStatusResponse(id=1, updated_at=1_700_000_000, status="Alpha")
    _mock_batches(command_fixture, [[status_resp]])

    command_fixture.import_game_statuses()

    assert GameStatus.objects.filter(igdb_id=1, status="Alpha").exists()


@pytest.mark.django_db()
def test_import_external_game_sources_creates_external_game_source(command_fixture: Command) -> None:
    """`import_external_game_sources` creates an `ExternalGameSource` row from a canned IGDB response."""
    source_resp = IGDBExternalGameSourceResponse(id=1, updated_at=1_700_000_000, name="Steam")
    _mock_batches(command_fixture, [[source_resp]])

    command_fixture.import_external_game_sources()

    assert ExternalGameSource.objects.filter(igdb_id=1, name_en="Steam").exists()


@pytest.mark.django_db()
def test_import_external_games_maps_external_game_source(command_fixture: Command) -> None:
    """`import_external_games` resolves `external_game_source` through the local `ExternalGameSource` mapping."""
    source = baker.make(ExternalGameSource, igdb_id=99)
    ext_resp = IGDBExternalGameResponse(
        id=1,
        updated_at=1_700_000_000,
        uid="730",
        external_game_source=99,
        url="https://store.steampowered.com/app/730",
    )
    _mock_batches(command_fixture, [[ext_resp]])

    command_fixture.import_external_games()

    ext_game = ExternalGame.objects.get(igdb_id=1)
    assert ext_game.external_game_source_id == source.id
    assert ext_game.external_id == "730"
