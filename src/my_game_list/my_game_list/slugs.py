"""This module contains the shared unique-slug generation helper."""

from typing import TYPE_CHECKING

from django.utils.text import slugify

if TYPE_CHECKING:
    from django.db.models import Model


def generate_unique_slug(model_cls: type[Model], base_value: str, *, exclude_pk: int | None = None) -> str:
    """Generate a slug from `base_value`, unique among `model_cls.objects`.

    `exclude_pk` excludes an instance's own row, so re-saving it unchanged doesn't
    treat its current slug as a collision against itself.
    """
    queryset = model_cls._default_manager.all()  # noqa: SLF001
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    base_slug = slugify(base_value)
    slug = base_slug
    counter = 1
    while queryset.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug
