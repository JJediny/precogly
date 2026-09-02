"""Regression test for precogly/precogly#406.

Canvas nodes carry the `trust_zone_id` of the zone they represent, and canvas data
comes from the caller. The sync looked that id up unfiltered and wrote the node's
label and trust level onto whatever row came back, so saving one organization's
diagram renamed and reclassified another's zone. The trust level feeds threat
analysis.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.diagrams.models import DFD
from apps.diagrams.services import _sync_nodes_to_trust_zones
from apps.organizations.models import Organization
from apps.systems.models import TrustZone
from apps.threat_models.models import ThreatModel

User = get_user_model()


class CanvasTrustZoneAdoptionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.attacker_org = Organization.objects.create(name="Kestrel")
        cls.victim_org = Organization.objects.create(name="Contoso")
        cls.user = User.objects.create_user(
            username="kestrel", email="user@kestrel.test", password="pw"
        )

        cls.threat_model = ThreatModel.objects.create(
            organization=cls.attacker_org,
            created_by=cls.user,
            name="Kestrel threat model",
        )
        cls.dfd = DFD.objects.create(
            name="Kestrel DFD", threat_model=cls.threat_model, is_primary=True
        )

        cls.victim_zone = TrustZone.objects.create(
            organization=cls.victim_org, name="Contoso DMZ", trust_level=20
        )

    def _sync(self, zone_id):
        """One trust-zone node naming `zone_id`, synced against Kestrel's diagram."""
        nodes = [
            {
                "id": "node-1",
                "type": "trustZone",
                "data": {
                    "label": "Adopted by Kestrel",
                    "trust_level": 99,
                    "trust_zone_id": zone_id,
                },
            }
        ]
        return _sync_nodes_to_trust_zones(self.dfd, nodes, self.threat_model)

    def test_another_tenants_zone_is_not_adopted(self):
        self._sync(self.victim_zone.id)

        self.victim_zone.refresh_from_db()
        self.assertEqual(
            (self.victim_zone.name, self.victim_zone.trust_level),
            ("Contoso DMZ", 20),
        )

    def test_the_unreachable_id_produces_a_zone_in_the_callers_organization(self):
        result = self._sync(self.victim_zone.id)

        adopted = TrustZone.objects.get(id=result["node_zone_map"]["node-1"])
        self.assertEqual(adopted.organization_id, self.attacker_org.id)
        self.assertEqual(adopted.name, "Adopted by Kestrel")

    def test_a_zone_the_caller_owns_is_still_updated(self):
        own = TrustZone.objects.create(
            organization=self.attacker_org, name="Kestrel DMZ", trust_level=50
        )

        self._sync(own.id)

        own.refresh_from_db()
        self.assertEqual((own.name, own.trust_level), ("Adopted by Kestrel", 99))
