"""
This migration populates the initial values for the GameMedia model.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

INITIAL_DATA = [
    {"name": "Steam"},
    {"name": "GOG"},
    {"name": "Epic Games Store"},
    {"name": "PlayStation Store"},
    {"name": "Physical copy"},
]


def populate_game_media(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """This function populates the initial values for the GameMedia model."""
    game_media_model = apps.get_model("games", "GameMedia")
    game_media_model.objects.bulk_create([game_media_model(**data) for data in INITIAL_DATA])


def remove_initial_game_media(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """This function removes the initial values for the GameMedia model."""
    game_media_model = apps.get_model("games", "GameMedia")
    game_media_model.objects.filter(name__in=[data["name"] for data in INITIAL_DATA]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0010_alter_gamemedia_options"),
    ]

    operations = [
        migrations.RunPython(code=populate_game_media, reverse_code=remove_initial_game_media),
    ]
