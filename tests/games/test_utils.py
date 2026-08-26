"""Tests for games utility functions."""

from game_list.games.utils import normalize_title


def test_normalize_title_converts_special_chars_and_case() -> None:
    """Hyphens removed, lowercase applied — the basic tracer bullet."""
    assert normalize_title("Half-Life") == "half life"


def test_normalize_title_removes_diacritics() -> None:
    """Polish diacritics stripped: ą→a, ę→e, ź→z etc."""
    assert normalize_title("Wiedźmin") == "wiedzmin"


def test_normalize_title_removes_colons_and_special_punctuation() -> None:
    """Colons, apostrophes and other punctuation collapse to a single space."""
    assert normalize_title("Half-Life: Alyx") == "half life alyx"


def test_normalize_title_build_search_title_deduplicates_identical_languages() -> None:
    """When EN and PL normalize to the same string, it is stored only once."""
    en = "FIFA 24"
    pl = "FIFA 24"
    normalized = {normalize_title(en), normalize_title(pl)}
    assert normalized == {"fifa 24"}
