from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("threats", "0012_cyclonedx_schema_enrichment"),
    ]

    operations = [
        migrations.AddField(
            model_name="instancecountermeasure",
            name="poam_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="POA&M item identifier (e.g. OSCAL poam-item.uuid or agency POA&M ID)",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="instancecountermeasure",
            name="scheduled_completion",
            field=models.DateField(
                blank=True,
                help_text="POA&M scheduled-completion-date (OSCAL POA&M); distinct from generic due_date",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="instancecountermeasure",
            name="required_for_release",
            field=models.BooleanField(
                default=False,
                help_text="ATO gate: control blocks release (e.g. FedRAMP showstopper)",
            ),
        ),
    ]
