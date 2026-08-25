"""Utility functions for the games application."""

import re
import unicodedata


def normalize_title(value: str) -> str:
    """Return a search-friendly version of a game title."""
    value = unicodedata.normalize("NFD", value)
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()
