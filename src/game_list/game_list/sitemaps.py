"""Sitemap views for search engine discovery of the public frontend pages.

The sitemaps list URLs of the *frontend* (``SITEMAP_BASE_URL``), not of the API. The gateway nginx routes
``/sitemap*.xml`` of the frontend host to these views, because a sitemap may only list URLs of its own host.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.views.decorators.cache import cache_page

from game_list.collections.models import Collection, CollectionVisibility
from game_list.games.models import Company, Game
from game_list.users.models import User

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from django.db.models import QuerySet

# The sitemap protocol allows at most 50 000 URLs per file.
SITEMAP_PAGE_SIZE = 50_000
CACHE_TIMEOUT = 60 * 60 * 24

STATIC_PATHS = ("/", "/search", "/release-calendar", "/faq", "/privacy", "/terms")

_XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n'
_URLSET_OPEN = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
_INDEX_OPEN = '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'


@dataclass(frozen=True)
class Section:
    """A group of frontend pages backed by one queryset, split into numbered sitemap files."""

    name: str
    path_prefix: str
    queryset: Callable[[], QuerySet[Any]]
    lastmod_field: str | None = None


def _public_games() -> QuerySet[Game]:
    return Game.objects.exclude(slug="")


def _public_companies() -> QuerySet[Company]:
    return Company.objects.exclude(slug="")


def _public_collections() -> QuerySet[Collection]:
    return Collection.objects.filter(
        visibility=CollectionVisibility.PUBLIC,
        is_moderated=False,
        user__is_active=True,
        user__is_banned=False,
    ).exclude(slug="")


def _public_profiles() -> QuerySet[User]:
    return User.objects.filter(is_active=True, is_banned=False, has_moderated_username=False).exclude(slug="")


SECTIONS: dict[str, Section] = {
    section.name: section
    for section in (
        Section("games", "/game", _public_games, "last_modified_at"),
        Section("companies", "/company", _public_companies, "igdb_updated_at"),
        Section("collections", "/collection", _public_collections, "last_modified_at"),
        Section("profiles", "/profile", _public_profiles),
    )
}


def _base_url() -> str:
    return str(settings.SITEMAP_BASE_URL).rstrip("/")


def _page_count(total: int) -> int:
    return max(1, -(-total // SITEMAP_PAGE_SIZE))


def _url_entry(loc: str, lastmod: datetime | None = None) -> str:
    lastmod_tag = f"<lastmod>{lastmod.date().isoformat()}</lastmod>" if lastmod else ""
    return f"<url><loc>{escape(loc)}</loc>{lastmod_tag}</url>\n"


def _xml_response(body: str) -> HttpResponse:
    return HttpResponse(body, content_type="application/xml; charset=utf-8")


@cache_page(CACHE_TIMEOUT)
def sitemap_index(request: HttpRequest) -> HttpResponse:  # noqa: ARG001
    """Return the sitemap index pointing to the static pages sitemap and every numbered section sitemap."""
    base = _base_url()
    locations = [f"{base}/sitemap-static.xml"]
    for section in SECTIONS.values():
        pages = _page_count(section.queryset().count())
        locations.extend(f"{base}/sitemap-{section.name}-{page}.xml" for page in range(1, pages + 1))
    body = _XML_HEADER + _INDEX_OPEN
    body += "".join(f"<sitemap><loc>{escape(loc)}</loc></sitemap>\n" for loc in locations)
    return _xml_response(body + "</sitemapindex>\n")


@cache_page(CACHE_TIMEOUT)
def sitemap_static(request: HttpRequest) -> HttpResponse:  # noqa: ARG001
    """Return the sitemap of the fixed, publicly reachable pages."""
    base = _base_url()
    body = _XML_HEADER + _URLSET_OPEN
    body += "".join(_url_entry(f"{base}{path}") for path in STATIC_PATHS)
    return _xml_response(body + "</urlset>\n")


@cache_page(CACHE_TIMEOUT)
def sitemap_section(request: HttpRequest, section: str, page: int) -> HttpResponse:  # noqa: ARG001
    """Return one numbered sitemap file of a section (games, companies, collections, profiles)."""
    config = SECTIONS.get(section)
    if config is None or page < 1:
        raise Http404

    fields = ["id", "slug"] + ([config.lastmod_field] if config.lastmod_field else [])
    start = (page - 1) * SITEMAP_PAGE_SIZE
    rows = list(config.queryset().order_by("id").values_list(*fields)[start : start + SITEMAP_PAGE_SIZE])
    if not rows and page > 1:
        raise Http404

    base = _base_url()
    body = _XML_HEADER + _URLSET_OPEN
    for row in rows:
        lastmod = row[2] if config.lastmod_field else None
        body += _url_entry(f"{base}{config.path_prefix}/{row[0]}/{row[1]}", lastmod)
    return _xml_response(body + "</urlset>\n")
