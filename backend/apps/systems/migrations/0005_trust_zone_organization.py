"""Give TrustZone and TrustBoundary an organization column.

Both tables held customer data with no forward path to an organization, so every
query that scoped them re-derived the owner through `components`, across two
nullable hops. precogly/precogly#404 read other tenants' zones that way and #406
wrote through it.

The backfill uses those same hops once more to set the column. A zone reachable from
two organizations is #406's case and picking either would hand one tenant's row to
another; a zone reachable from none has no owner to record. Both raise and name the
rows. Nothing is deleted here — `manage.py trust_zone_owners` lists them.
"""

from django.db import migrations, models
import django.db.models.deletion


def _zone_owners(apps):
    """zone id -> the set of organization ids reachable from its components.

    Two queries rather than a walk per zone. Both hops are nullable, so a component
    can contribute one owner, two, or none.
    """
    Component = apps.get_model("systems", "OrgsystemComponent")
    linked = Component.objects.filter(trust_zone__isnull=False)

    owners = {}
    for field in ("orgsystem__organization_id", "threat_model__organization_id"):
        rows = linked.exclude(**{field.split("__organization_id")[0]: None})
        for zone_id, org_id in rows.values_list("trust_zone_id", field):
            if org_id is not None:
                owners.setdefault(zone_id, set()).add(org_id)
    return owners


def _refuse(kind, rows):
    raise RuntimeError(
        f"Cannot migrate: {len(rows)} trust {kind}.\n"
        f"  {rows}\n"
        "A zone reachable from two organizations is precogly/precogly#406 and this "
        "migration will not choose between them; a zone reachable from none has no "
        "owner to record. Resolve or remove these rows, then run migrate again. "
        "`manage.py trust_zone_owners` reports them without changing anything."
    )


def set_owners(apps, schema_editor):
    TrustZone = apps.get_model("systems", "TrustZone")
    TrustBoundary = apps.get_model("systems", "TrustBoundary")

    owners = _zone_owners(apps)
    resolved, ambiguous, ownerless = {}, [], []

    for zone_id in TrustZone.objects.values_list("id", flat=True):
        found = owners.get(zone_id, set())
        if len(found) == 1:
            resolved[zone_id] = found.pop()
        elif found:
            ambiguous.append(zone_id)
        else:
            ownerless.append(zone_id)

    if ambiguous:
        _refuse("zones reachable from more than one organization", ambiguous)
    if ownerless:
        _refuse("zones reachable from no organization", ownerless)

    for zone_id, org_id in resolved.items():
        TrustZone.objects.filter(id=zone_id).update(organization_id=org_id)

    # A boundary joins two zones that are separate rows, so they can disagree even
    # once every zone is resolved.
    split = []
    for boundary_id, a, b in TrustBoundary.objects.values_list(
        "id", "zone_a_id", "zone_b_id"
    ):
        ends = {resolved[a], resolved[b]}
        if len(ends) != 1:
            split.append(boundary_id)
        else:
            TrustBoundary.objects.filter(id=boundary_id).update(
                organization_id=ends.pop()
            )

    if split:
        _refuse("boundaries whose two zones belong to different organizations", split)


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("systems", "0004_cyclonedx_schema_enrichment"),
    ]

    operations = [
        migrations.AddField(
            model_name="trustzone",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="trust_zones",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="trustboundary",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="trust_boundaries",
                to="organizations.organization",
            ),
        ),
        migrations.RunPython(set_owners, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="trustzone",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="trust_zones",
                to="organizations.organization",
            ),
        ),
        migrations.AlterField(
            model_name="trustboundary",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="trust_boundaries",
                to="organizations.organization",
            ),
        ),
    ]
