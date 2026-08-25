"""IGDB related functions."""

from enum import StrEnum


class IGDBImageSize(StrEnum):
    """IGDB image size for the image URL."""

    COVER_SMALL_90_128 = "cover_small"
    SCREENSHOT_MED_569_320 = "screenshot_med"
    COVER_BIG_264_374 = "cover_big"
    LOGO_MED_284_160 = "logo_med"
    SCREENSHOT_BIG_889_500 = "screenshot_big"
    SCREENSHOT_HUGE_1280_720 = "screenshot_huge"
    THUMB_90_90 = "thumb"
    MICRO_35_35 = "micro"
    P720_1280_720 = "720p"
    P1080_1920_1080 = "1080p"


def get_image_url(image_id: str, size: IGDBImageSize) -> str:
    """Get the image URL for the given image ID and size.

    Args:
        image_id (str): The ID of the image.
        size (IGDBImageSize): The size of the image.

    Returns:
        str: The image URL.
    """
    return f"https://images.igdb.com/igdb/image/upload/t_{size.value}/{image_id}.png"
