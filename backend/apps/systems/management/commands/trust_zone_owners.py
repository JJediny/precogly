"""List trust zones with no owner, or with more than one.

`systems.0005_trust_zone_organization` derives each zone's organization through its
components, where both hops are nullable. A zone reachable from two organizations is
precogly/precogly#406; one reachable from none has nothing to record. The migration
raises on either, and this shows which rows it means.

Read-only: what to do with them is a decision about customer data.
"""

from django.core.management.base import BaseCommand

from apps.systems.models import OrgsystemComponent, TrustZone


class Command(BaseCommand):
    help = "List trust zones with no owner, or more than one, before migrating."

    def handle(self, *args, **options):
        owners = self._owners()

        ownerless, ambiguous = [], []
        for zone in TrustZone.objects.all().order_by("id"):
            found = owners.get(zone.id, set())
            if not found:
                ownerless.append((zone, found))
            elif len(found) > 1:
                ambiguous.append((zone, found))

        total = TrustZone.objects.count()
        self.stdout.write(f"{total} trust zones")

        self._report(
            "reachable from more than one organization", ambiguous, show_orgs=True
        )
        self._report("reachable from no organization", ownerless, show_orgs=False)

        if total and not ownerless and not ambiguous:
            self.stdout.write(self.style.SUCCESS("  every zone has exactly one owner"))

    @staticmethod
    def _owners():
        """zone id -> organization ids reachable through its components.

        The same derivation the migration uses. Both hops are nullable, which is how
        a zone ends up with no owner.
        """
        linked = OrgsystemComponent.objects.filter(trust_zone__isnull=False)
        owners = {}
        for relation in ("orgsystem", "threat_model"):
            rows = linked.exclude(**{relation: None}).values_list(
                "trust_zone_id", f"{relation}__organization_id"
            )
            for zone_id, org_id in rows:
                if org_id is not None:
                    owners.setdefault(zone_id, set()).add(org_id)
        return owners

    def _report(self, label, rows, show_orgs):
        if not rows:
            return
        self.stdout.write(self.style.ERROR(f"\n{len(rows)} {label}:"))
        for zone, found in rows:
            suffix = f"  organizations {sorted(found)}" if show_orgs else ""
            self.stdout.write(f"  #{zone.id}  {zone.name!r}{suffix}")
