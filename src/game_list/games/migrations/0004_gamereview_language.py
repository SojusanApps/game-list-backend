from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0003_add_xbox_game_media"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamereview",
            name="language",
            field=models.CharField(
                choices=[("en", "English"), ("pl", "Polish")],
                default="en",
                help_text="The language the review text is written in (English, Polish).",
                max_length=2,
                verbose_name="language",
            ),
            preserve_default=False,
        ),
    ]
