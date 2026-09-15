"""
Compliance drift detection and refresh service.

Compares instance-level compliance mappings against their library sources
and syncs them when requested.
"""

from django.db import transaction

from apps.compliance.models import CountermeasureLibraryStandard
from apps.threats.models import (
    InstanceCountermeasure,
    InstanceCountermeasureStandard,
)


def _get_non_orphaned_countermeasures(threat_model):
    """
    Return non-orphaned countermeasures scoped to this threat model,
    with their library standards prefetched.

    Uses direct threat_model FK for scoping. Each countermeasure instance
    appears once even if shared across multiple threats.
    """
    return (
        InstanceCountermeasure.objects.filter(
            threat_model=threat_model,
            countermeasure_library__isnull=False,
        )
        .distinct()
        .select_related("countermeasure_library")
        .prefetch_related(
            "instance_standard_mappings",
            "countermeasure_library__standard_mappings__requirement__framework",
        )
    )


def _compute_drift_for_countermeasure(instance_mappings, library_standards):
    """
    Compare instance mappings against library standards for a single
    countermeasure. Returns (additions, removals, updates) counts.
    """
    # Build lookup: requirement_id -> sufficiency for instance mappings
    instance_by_req = {
        mapping.requirement_id: mapping.sufficiency
        for mapping in instance_mappings
        if mapping.requirement_id is not None
    }

    # Build lookup: requirement_id -> sufficiency for library standards
    library_by_req = {ls.requirement_id: ls.sufficiency for ls in library_standards}

    additions = 0
    removals = 0
    updates = 0

    # Standards in library but not in instance -> additions
    for req_id, sufficiency in library_by_req.items():
        if req_id not in instance_by_req:
            additions += 1
        elif instance_by_req[req_id] != sufficiency:
            updates += 1

    # Standards in instance but not in library -> removals
    for req_id in instance_by_req:
        if req_id not in library_by_req:
            removals += 1

    return additions, removals, updates


def check_compliance_drift(threat_model):
    """
    Check for compliance drift between instance and library mappings.

    Returns a summary dict with drift statistics.
    """
    countermeasures = _get_non_orphaned_countermeasures(threat_model)

    total_additions = 0
    total_removals = 0
    total_updates = 0
    affected_countermeasures = 0

    for cm in countermeasures:
        instance_mappings = cm.instance_standard_mappings.all()
        # NAVE PATCH (precogly/precogly#338): `standard_mappings` is
        # prefetched (see _get_non_orphaned_countermeasures()), so filter
        # in Python rather than with .exclude() -- adding a queryset filter
        # here would bypass the prefetch cache and re-query per
        # countermeasure. Orphaned rows (requirement=None, left behind by
        # a renamed/typo'd section_code on reimport instead of being
        # CASCADE-deleted -- see apps/compliance/models.py) aren't real
        # drift candidates and must be excluded, not just null-guarded:
        # left in, `requirement_id=None` would be treated as a distinct
        # "requirement" both compute functions key their lookups by,
        # producing a phantom addition/removal for every orphaned row.
        library_standards = [
            ls
            for ls in cm.countermeasure_library.standard_mappings.all()
            if ls.requirement_id is not None
        ]
        additions, removals, updates = _compute_drift_for_countermeasure(
            instance_mappings, library_standards
        )
        if additions or removals or updates:
            affected_countermeasures += 1
            total_additions += additions
            total_removals += removals
            total_updates += updates

    has_drift = (total_additions + total_removals + total_updates) > 0

    return {
        "has_drift": has_drift,
        "total_additions": total_additions,
        "total_removals": total_removals,
        "total_updates": total_updates,
        "affected_countermeasures": affected_countermeasures,
    }


def _sync_instance_standards(countermeasure):
    """
    Sync a single countermeasure's instance standards with its library source.
    Returns (added, removed, updated) counts.
    """
    # NAVE PATCH (precogly/precogly#338): exclude orphaned mappings
    # (requirement=None, left behind by a renamed/typo'd section_code on
    # reimport instead of being CASCADE-deleted -- see apps/compliance/
    # models.py). A fresh queryset here (unlike _compute_drift_for_
    # countermeasure's prefetched one above), so filtering at the DB is
    # fine. Without this, `ls.requirement.section_code` etc. below would
    # raise AttributeError on the first orphaned row.
    library_standards = (
        CountermeasureLibraryStandard.objects.filter(
            countermeasure_library=countermeasure.countermeasure_library,
        )
        .exclude(requirement__isnull=True)
        .select_related("requirement", "requirement__framework")
    )

    instance_mappings = countermeasure.instance_standard_mappings.all()

    # Build lookups
    instance_by_req = {
        mapping.requirement_id: mapping
        for mapping in instance_mappings
        if mapping.requirement_id is not None
    }
    library_by_req = {ls.requirement_id: ls for ls in library_standards}

    added = 0
    removed = 0
    updated = 0

    # Add missing mappings from library
    to_create = []
    for req_id, ls in library_by_req.items():
        if req_id not in instance_by_req:
            to_create.append(
                InstanceCountermeasureStandard(
                    countermeasure=countermeasure,
                    requirement=ls.requirement,
                    sufficiency=ls.sufficiency,
                    section_code=ls.requirement.section_code,
                    framework_name=ls.requirement.framework.name,
                    requirement_description=ls.requirement.description,
                )
            )
        elif instance_by_req[req_id].sufficiency != ls.sufficiency:
            # Update changed sufficiency
            mapping = instance_by_req[req_id]
            mapping.sufficiency = ls.sufficiency
            mapping.save(update_fields=["sufficiency"])
            updated += 1

    if to_create:
        InstanceCountermeasureStandard.objects.bulk_create(
            to_create, ignore_conflicts=True
        )
        added = len(to_create)

    # Remove mappings no longer in library
    orphaned_req_ids = [
        req_id for req_id in instance_by_req if req_id not in library_by_req
    ]
    if orphaned_req_ids:
        removed = countermeasure.instance_standard_mappings.filter(
            requirement_id__in=orphaned_req_ids
        ).delete()[0]

    return added, removed, updated


@transaction.atomic
def refresh_compliance_standards(threat_model):
    """
    Sync all instance-level compliance mappings with their library sources.

    Adds missing mappings, removes deleted mappings, and updates changed
    sufficiency values. Returns a summary of changes made.
    """
    countermeasures = _get_non_orphaned_countermeasures(threat_model)

    total_added = 0
    total_removed = 0
    total_updated = 0
    countermeasures_affected = 0

    for cm in countermeasures:
        added, removed, updated = _sync_instance_standards(cm)
        if added or removed or updated:
            countermeasures_affected += 1
            total_added += added
            total_removed += removed
            total_updated += updated

    return {
        "standards_added": total_added,
        "standards_removed": total_removed,
        "standards_updated": total_updated,
        "countermeasures_affected": countermeasures_affected,
    }
