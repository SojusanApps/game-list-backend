"""Tests for games models."""

from typing import TYPE_CHECKING

import pytest
from django.db import IntegrityError
from django.utils.translation import override
from model_bakery import baker

from my_game_list.games.models import (
    Company,
    Game,
    GameFollow,
    GameList,
    GameMedia,
    GameReview,
    Genre,
    Platform,
    TranslationSuggestion,
    TranslationSuggestionField,
    TranslationSuggestionStatus,
)

if TYPE_CHECKING:
    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_company_dunder_str() -> None:
    """Test the `Company` dunder str method."""
    developer = baker.make(Company)
    assert str(developer) == developer.name


@pytest.mark.django_db()
def test_game_follow_dunder_str(game_follow_fixture: GameFollow) -> None:
    """Test the `GameFollow` dunder str method."""
    assert str(game_follow_fixture) == f"{game_follow_fixture.user.username} - {game_follow_fixture.game.title}"


@pytest.mark.django_db()
def test_game_list_dunder_str(game_list_fixture: GameList) -> None:
    """Test the `GameList` dunder str method."""
    assert str(game_list_fixture) == f"{game_list_fixture.user.username} - {game_list_fixture.game.title}"


@pytest.mark.django_db()
def test_game_review_dunder_str(game_review_fixture: GameReview) -> None:
    """Test the `GameReview` dunder str method."""
    assert str(game_review_fixture) == f"{game_review_fixture.user.username} - {game_review_fixture.game.title}"


@pytest.mark.django_db()
def test_game_dunder_str(game_fixture: Game) -> None:
    """Test the `Game` dunder str method."""
    assert str(game_fixture) == game_fixture.title


@pytest.mark.django_db()
def test_game_save_populates_search_title() -> None:
    """Game.save() builds search_title from both language titles."""
    game = baker.make(Game, title_en="Wiedźmin", title_pl="The Witcher")
    assert game.search_title == "the witcher wiedzmin"


@pytest.mark.django_db()
def test_game_save_deduplicates_search_title_when_titles_identical() -> None:
    """When EN and PL titles normalize identically, search_title is not duplicated."""
    game = baker.make(Game, title_en="FIFA 24", title_pl="FIFA 24")
    assert game.search_title == "fifa 24"


@pytest.mark.django_db()
def test_genre_dunder_str() -> None:
    """Test the `Genre` dunder str method."""
    genre = baker.make(Genre)
    assert str(genre) == genre.name


@pytest.mark.django_db()
def test_platform_dunder_str() -> None:
    """Test the `Platform` dunder str method."""
    platform = baker.make(Platform)
    assert str(platform) == platform.name


@pytest.mark.django_db()
def test_game_media_dunder_str() -> None:
    """Test the `GameMedia` dunder str method."""
    game_media = baker.make(GameMedia)
    assert str(game_media) == game_media.name


@pytest.mark.django_db()
def test_genre_name_returns_polish_value_when_polish_is_active() -> None:
    """Genre.name proxies to the Polish translation when the active language is Polish."""
    genre = baker.make(Genre, name_en="Action", name_pl="Akcja")
    with override("pl"):
        assert genre.name == "Akcja"


@pytest.mark.django_db()
def test_game_slug_uses_english_title_when_polish_is_active() -> None:
    """Game.slug is always derived from the English title, regardless of the active language at save time."""
    with override("pl"):
        game = baker.make(Game, title_en="The Witcher", title_pl="Wiedzmin", slug="")
    assert game.slug == "the-witcher"


@pytest.mark.django_db()
def test_company_slug_uses_english_name_when_polish_is_active() -> None:
    """Company.slug is always derived from the English name, regardless of the active language at save time."""
    with override("pl"):
        company = baker.make(Company, name_en="CD Projekt", name_pl="CD Projekt PL", slug="")
    assert company.slug == "cd-projekt"


@pytest.mark.django_db()
def test_translation_suggestion_dunder_str(game_fixture: Game) -> None:
    """Test the `TranslationSuggestion` dunder str method."""
    suggestion = baker.make(TranslationSuggestion, game=game_fixture, field=TranslationSuggestionField.SUMMARY)
    assert str(suggestion) == f"{game_fixture.title} - {suggestion.field} ({suggestion.status})"


@pytest.mark.django_db()
def test_translation_suggestion_unique_pending_constraint_blocks_duplicate_at_db_level(
    game_fixture: Game,
    user_fixture: UserModel,
) -> None:
    """The conditional UniqueConstraint blocks a second pending row for the same user+game+field.

    This bypasses the serializer entirely to prove the invariant is enforced by the database,
    not just by application-level validation (which could otherwise be raced).
    """
    baker.make(
        TranslationSuggestion,
        game=game_fixture,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=user_fixture,
        status=TranslationSuggestionStatus.PENDING,
    )

    with pytest.raises(IntegrityError):
        baker.make(
            TranslationSuggestion,
            game=game_fixture,
            field=TranslationSuggestionField.SUMMARY,
            submitted_by=user_fixture,
            status=TranslationSuggestionStatus.PENDING,
        )
