from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("systems", "0005_trust_zone_organization"),
    ]

    operations = [
        migrations.AddField(
            model_name="componentlibrary",
            name="icon_svg",
            field=models.TextField(blank=True, default=""),
        ),
    ]
