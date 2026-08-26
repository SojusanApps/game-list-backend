"""Tests for IGDB integration helpers."""

from game_list.game_list.igdb_integration import IGDBImageSize, get_image_url


def test_get_image_url_builds_the_expected_igdb_cdn_url() -> None:
    """The URL is built from the IGDB CDN base, the requested size's value, and the raw image id."""
    url = get_image_url("abc123", IGDBImageSize.COVER_BIG_264_374)

    assert url == "https://images.igdb.com/igdb/image/upload/t_cover_big/abc123.png"
