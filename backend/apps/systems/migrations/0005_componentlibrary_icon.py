from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("systems", "0004_cyclonedx_schema_enrichment"),
    ]

    operations = [
        migrations.AddField(
            model_name="componentlibrary",
            name="icon",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Optional icon config for this component (same shape as "
                    "LibraryPack.icon). If empty, the component inherits the "
                    "pack icon or the vendor default (aws/azure/gcp)."
                ),
            ),
        ),
    ]
