"""Fuzzy game title search.

Trigram similarity is used only in SQL for candidate retrieval (recall), because trigram
scores are biased toward shorter strings: "witchre" scores higher against "witch" than
against "witcher", so no trigram-based ranking can put the intended game first. The
actual ranking happens in Python with Damerau-Levenshtein similarity, which treats the
"re" <-> "er" transposition as a single edit, and ties are broken by the game's members
count so well-known games win among equally good matches.
"""

from typing import Any

from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models import Case, QuerySet, Value, When
from rapidfuzz.distance import DamerauLevenshtein

from my_game_list.games.utils import normalize_title

# How many trigram candidates are fetched from the database for re-ranking.
CANDIDATE_POOL_SIZE = 200
# Word similarity threshold for a row to become a candidate; kept loose on purpose,
# precision comes from the Python re-ranking.
CANDIDATE_MIN_WORD_SIMILARITY = 0.2
# Minimal Damerau-Levenshtein based score for a candidate to appear in the results.
MIN_SCORE = 0.55
# Applied to matches against a fragment of the title, so that a full-title match
# always outranks a partial one ("The Witcher" query: the game "The Witcher" must
# come before "The Witcher 3: Wild Hunt").
PARTIAL_MATCH_PENALTY = 0.95


def score_title_match(query: str, title: str) -> float:
    """Score how well a normalized query matches a single normalized title, in [0, 1].

    Both arguments must already be normalized with `normalize_title`.
    """
    if not query or not title:
        return 0.0
    if query == title:
        return 1.0
    similarity = DamerauLevenshtein.normalized_similarity
    score = max(
        # Whole-title match with typos.
        similarity(query, title),
        # Word order must not matter: "life half" matches "half life".
        similarity(" ".join(sorted(query.split())), " ".join(sorted(title.split()))),
        # Search-as-you-type: the query is a (possibly misspelled) prefix of the title.
        similarity(query, title[: len(query)]) * PARTIAL_MATCH_PENALTY,
    )
    # Align the query against every window of consecutive title words, so that
    # "the witchre" is scored against "the witcher" instead of the whole
    # "the witcher 3 wild hunt".
    title_words = title.split()
    window_size = len(query.split())
    for start in range(len(title_words) - window_size + 1):
        window = " ".join(title_words[start : start + window_size])
        window_score = max(similarity(query, window), similarity(query, window[: len(query)]))
        score = max(score, window_score * PARTIAL_MATCH_PENALTY)
    return score


def ranked_title_match_pks(queryset: QuerySet[Any], value: str, game_field: str = "") -> list[Any]:
    """Return the pks of queryset rows whose game title fuzzy-matches `value`, best match first.

    `game_field` is the lookup prefix from the queryset's model to the `Game` model:
    empty for `Game` querysets, "game__" for `GameList` querysets.
    """
    normalized = normalize_title(value)
    if not normalized:
        return []
    candidates = (
        queryset.alias(word_similarity=TrigramWordSimilarity(normalized, f"{game_field}search_title"))
        .filter(word_similarity__gte=CANDIDATE_MIN_WORD_SIMILARITY)
        .order_by("-word_similarity")
        .values_list(
            "pk",
            f"{game_field}title_en",
            f"{game_field}title_pl",
            f"{game_field}stats__members_count",
        )[:CANDIDATE_POOL_SIZE]
    )
    ranked: dict[Any, tuple[float, int]] = {}
    for pk, title_en, title_pl, members_count in candidates:
        score = max(
            score_title_match(normalized, normalize_title(title_en or "")),
            score_title_match(normalized, normalize_title(title_pl or "")),
        )
        if score >= MIN_SCORE:
            # Round so that near-identical scores tie and popularity decides.
            ranked[pk] = max(ranked.get(pk, (0.0, 0)), (round(score, 2), members_count or 0))
    return sorted(ranked, key=lambda pk: ranked[pk], reverse=True)


def filter_queryset_by_title(queryset: QuerySet[Any], value: str, game_field: str = "") -> QuerySet[Any]:
    """Filter a queryset by a fuzzy title match and order it best match first.

    `game_field` is the lookup prefix from the queryset's model to the `Game` model:
    empty for `Game` querysets, "game__" for `GameList` querysets.
    """
    ordered_pks = ranked_title_match_pks(queryset, value, game_field)
    if not ordered_pks:
        return queryset.none()
    position = Case(*[When(pk=pk, then=Value(index)) for index, pk in enumerate(ordered_pks)])
    return queryset.filter(pk__in=ordered_pks).order_by(position)
