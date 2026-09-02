"""Regression tests for precogly/precogly#404.

`?threat_model=` on the trust-zone list replaced the organization join instead of
narrowing it, so any authenticated user could name any threat model and read that
tenant's zones. Zones now carry an `organization` and the filter applies on top of
it.

The tests asserting that own zones are still returned exist because a queryset
returning nothing would pass the leak assertions too.
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.organizations.models import Organization, OrganizationMember
from apps.systems.models import OrgsystemComponent, TrustBoundary, TrustZone
from apps.threat_models.models import ThreatModel

User = get_user_model()


class TrustZoneScopingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="Acme")
        cls.other_organization = Organization.objects.create(name="Globex")
        cls.member = User.objects.create_user(
            username="member", email="member@acme.test", password="pw"
        )
        OrganizationMember.objects.create(
            organization=cls.organization, user=cls.member
        )

        cls.threat_model = ThreatModel.objects.create(
            organization=cls.organization,
            created_by=cls.member,
            name="Acme threat model",
        )
        cls.other_threat_model = ThreatModel.objects.create(
            organization=cls.other_organization,
            created_by=cls.member,
            name="Globex threat model",
        )

        cls.own_zone = cls._zone(cls.organization, cls.threat_model, "Acme DMZ")
        cls.other_zone = cls._zone(
            cls.other_organization, cls.other_threat_model, "Globex DMZ"
        )

    def setUp(self):
        self.client.force_authenticate(self.member)

    @classmethod
    def _zone(cls, organization, threat_model, name):
        """A zone with a component attached, so the ?threat_model= join can reach it."""
        zone = TrustZone.objects.create(organization=organization, name=name)
        OrgsystemComponent.objects.create(
            name=f"{name} component", threat_model=threat_model, trust_zone=zone
        )
        return zone

    def _names(self, response):
        rows = response.data
        if isinstance(rows, dict):
            rows = rows["results"]
        return {row["name"] for row in rows}

    def test_naming_another_tenants_threat_model_returns_nothing(self):
        response = self.client.get(
            "/api/trust-zones/", {"threat_model": self.other_threat_model.id}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._names(response), set())

    def test_the_filter_still_returns_own_zones(self):
        response = self.client.get(
            "/api/trust-zones/", {"threat_model": self.threat_model.id}
        )

        self.assertEqual(self._names(response), {"Acme DMZ"})

    def test_unfiltered_list_is_scoped_to_the_callers_organization(self):
        response = self.client.get("/api/trust-zones/")

        self.assertEqual(self._names(response), {"Acme DMZ"})


class TrustBoundaryScopingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="Acme")
        cls.other_organization = Organization.objects.create(name="Globex")
        cls.member = User.objects.create_user(
            username="member", email="member@acme.test", password="pw"
        )
        OrganizationMember.objects.create(
            organization=cls.organization, user=cls.member
        )

        cls.own = cls._boundary(cls.organization, "Acme edge")
        cls.other = cls._boundary(cls.other_organization, "Globex edge")

    def setUp(self):
        self.client.force_authenticate(self.member)

    @classmethod
    def _boundary(cls, organization, label):
        zone_a = TrustZone.objects.create(organization=organization, name=f"{label} a")
        zone_b = TrustZone.objects.create(organization=organization, name=f"{label} b")
        return TrustBoundary.objects.create(
            organization=organization, zone_a=zone_a, zone_b=zone_b, label=label
        )

    def test_list_is_scoped_to_the_callers_organization(self):
        response = self.client.get("/api/trust-boundaries/")

        rows = response.data
        if isinstance(rows, dict):
            rows = rows["results"]
        self.assertEqual({row["label"] for row in rows}, {"Acme edge"})
