"""
Migration: Unify countermeasure models

Merges ComponentInstanceCountermeasure + FlowInstanceCountermeasure into
InstanceCountermeasure, and replaces two junction tables with a single
polymorphic CountermeasureThreatLink table.

No production data exists (v0.2.0), so this is a destructive migration.
"""

import django.core.validators
import django.db.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("threats", "0009_shared_countermeasures_m2m"),
        ("threat_models", "0001_initial"),
        ("compliance", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # -------------------------------------------------------
        # 1. Drop old models that reference the soon-to-be-deleted
        #    component/flow countermeasure models
        # -------------------------------------------------------

        # Drop old junction tables
        migrations.DeleteModel(name="ComponentCountermeasureThreatLink"),
        migrations.DeleteModel(name="FlowCountermeasureThreatLink"),

        # Drop old verification test join tables
        migrations.DeleteModel(name="ComponentInstanceCountermeasureTest"),
        migrations.DeleteModel(name="FlowInstanceCountermeasureTest"),

        # Drop old standard mapping tables
        migrations.DeleteModel(name="ComponentInstanceCountermeasureStandard"),
        migrations.DeleteModel(name="FlowInstanceCountermeasureStandard"),

        # Drop old comment model (will be recreated)
        migrations.DeleteModel(name="CountermeasureComment"),

        # Drop old pentest finding model (will be recreated)
        migrations.DeleteModel(name="PentestFinding"),

        # Drop old countermeasure models
        migrations.DeleteModel(name="ComponentInstanceCountermeasure"),
        migrations.DeleteModel(name="FlowInstanceCountermeasure"),

        # -------------------------------------------------------
        # 2. Create unified InstanceCountermeasure
        # -------------------------------------------------------
        migrations.CreateModel(
            name="InstanceCountermeasure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(
                    choices=[
                        ("gap", "Gap"),
                        ("planned", "Planned"),
                        ("in_progress", "In Progress"),
                        ("verified", "Verified"),
                        ("waived", "Waived"),
                        ("platform", "Platform"),
                    ],
                    default="gap",
                    max_length=20,
                )),
                ("evidence_url", models.URLField(blank=True)),
                ("required_for_release", models.BooleanField(default=False)),
                ("countermeasure_name", models.CharField(blank=True, help_text="Copied from CountermeasureLibrary.name on creation", max_length=255)),
                ("countermeasure_description", models.TextField(blank=True, help_text="Copied from CountermeasureLibrary.description on creation")),
                ("control_type", models.CharField(blank=True, help_text="Copied from CountermeasureLibrary.control_type on creation", max_length=50)),
                ("effectiveness", models.FloatField(
                    blank=True,
                    null=True,
                    validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)],
                    help_text="User-assessed control effectiveness (0.0-1.0). Null = not yet assessed.",
                )),
                ("priority", models.CharField(blank=True, default="none", max_length=10)),
                ("due_date", models.DateField(blank=True, null=True, help_text="Target completion date")),
                ("external_ticket_url", models.URLField(blank=True, help_text="Link to Jira/GitHub/etc. ticket")),
                ("format_metadata", models.JSONField(blank=True, default=dict)),
                ("is_inherited", models.BooleanField(default=False)),
                ("inherited_from_component_name", models.CharField(blank=True, max_length=255)),
                ("inherited_from_zone_name", models.CharField(blank=True, max_length=255)),
                ("threat_model", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="countermeasures",
                    to="threat_models.threatmodel",
                )),
                ("countermeasure_library", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="instances",
                    to="threats.countermeasurelibrary",
                    help_text="Null means orphaned/custom countermeasure (library item was removed)",
                )),
                ("verified_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="verified_countermeasures",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("assigned_owner", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assigned_countermeasures",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),

        # -------------------------------------------------------
        # 3. Create polymorphic CountermeasureThreatLink
        # -------------------------------------------------------
        migrations.CreateModel(
            name="CountermeasureThreatLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("countermeasure", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="threat_links",
                    to="threats.instancecountermeasure",
                )),
                ("component_threat", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="countermeasure_links",
                    to="threats.componentinstancethreat",
                )),
                ("flow_threat", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="countermeasure_links",
                    to="threats.dataflowinstancethreat",
                )),
            ],
            options={
                "ordering": ["display_order", "created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="countermeasurethreatlink",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(component_threat__isnull=False, flow_threat__isnull=True)
                    | models.Q(component_threat__isnull=True, flow_threat__isnull=False)
                ),
                name="cm_link_exactly_one_threat_fk",
            ),
        ),
        migrations.AddConstraint(
            model_name="countermeasurethreatlink",
            constraint=models.UniqueConstraint(
                fields=["countermeasure", "component_threat"],
                condition=models.Q(component_threat__isnull=False),
                name="unique_cm_component_threat_link",
            ),
        ),
        migrations.AddConstraint(
            model_name="countermeasurethreatlink",
            constraint=models.UniqueConstraint(
                fields=["countermeasure", "flow_threat"],
                condition=models.Q(flow_threat__isnull=False),
                name="unique_cm_flow_threat_link",
            ),
        ),

        # -------------------------------------------------------
        # 4. Create unified InstanceCountermeasureTest
        # -------------------------------------------------------
        migrations.CreateModel(
            name="InstanceCountermeasureTest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tested_at", models.DateTimeField(auto_now_add=True)),
                ("countermeasure", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="tests",
                    to="threats.instancecountermeasure",
                )),
                ("verification_test", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="countermeasure_tests",
                    to="threats.verificationtest",
                )),
            ],
            options={
                "ordering": ["-tested_at"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="instancecountermeasuretest",
            unique_together={("countermeasure", "verification_test")},
        ),

        # -------------------------------------------------------
        # 5. Recreate CountermeasureComment with single FK
        # -------------------------------------------------------
        migrations.CreateModel(
            name="CountermeasureComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("body", models.TextField()),
                ("change_summary", models.CharField(blank=True, max_length=255)),
                ("author", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="countermeasure_comments",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("countermeasure", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="comments",
                    to="threats.instancecountermeasure",
                )),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),

        # -------------------------------------------------------
        # 6. Recreate PentestFinding with single countermeasure FK
        # -------------------------------------------------------
        migrations.CreateModel(
            name="PentestFinding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("finding_description", models.TextField()),
                ("severity", models.CharField(max_length=20)),
                ("reconciliation_status", models.CharField(
                    choices=[
                        ("matched", "Matched"),
                        ("unpredicted", "Unpredicted"),
                        ("false_positive", "False Positive"),
                    ],
                    default="unpredicted",
                    max_length=20,
                )),
                ("threat_model", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="pentest_findings",
                    to="threat_models.threatmodel",
                )),
                ("matched_threat_library", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="matched_pentest_findings",
                    to="threats.threatlibrary",
                )),
                ("matched_countermeasure", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="pentest_findings",
                    to="threats.instancecountermeasure",
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),

        # -------------------------------------------------------
        # 7. Create unified InstanceCountermeasureStandard
        # -------------------------------------------------------
        migrations.CreateModel(
            name="InstanceCountermeasureStandard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sufficiency", models.CharField(
                    choices=[("full", "Full"), ("partial", "Partial")],
                    default="partial",
                    max_length=10,
                )),
                ("section_code", models.CharField(blank=True, default="", max_length=50)),
                ("framework_name", models.CharField(blank=True, default="", max_length=255)),
                ("requirement_description", models.TextField(blank=True, default="")),
                ("countermeasure", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="instance_standard_mappings",
                    to="threats.instancecountermeasure",
                )),
                ("requirement", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="instance_countermeasure_mappings",
                    to="compliance.standardrequirement",
                )),
            ],
            options={
                "verbose_name": "Countermeasure compliance mapping",
                "verbose_name_plural": "Countermeasure compliance mappings",
            },
        ),
        migrations.AlterUniqueTogether(
            name="instancecountermeasurestandard",
            unique_together={("countermeasure", "requirement")},
        ),
    ]
