from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("packs", "0002_pendingtaxonomyoverlay"),
    ]

    operations = [
        migrations.AddField(
            model_name="librarypack",
            name="icon",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Optional icon config for the pack (see @thesvg/react). Must be an "
                    "object with at least a 'slug' key, e.g. {\"slug\": \"aws\", "
                    "\"variant\": \"mono\", \"className\": \"h-5 w-5\"}."
                ),
            ),
        ),
    ]
