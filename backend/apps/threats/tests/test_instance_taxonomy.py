"""Tests for InstanceThreatTaxonomyEntry model and viewset."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.organizations.models import Organization, OrganizationMember
from apps.systems.models import OrgsystemComponent
from apps.threat_models.models import ThreatModel
from apps.threats.models import (
    ComponentInstanceThreat,
    ExternalTaxonomy,
    InstanceThreatTaxonomyEntry,
    TaxonomyEntry,
    ThreatLibrary,
    ThreatLibraryTaxonomyEntry,
)

User = get_user_model()


class InstanceTaxonomyTestCase(TestCase):
    """Base class with shared fixtures."""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Test Org", domain="test.org")
        cls.user = User.objects.create_user(
            username="testuser", email="test@test.org", password="testpass123"
        )
        OrganizationMember.objects.create(
            organization=cls.org, user=cls.user, role="security_team"
        )

        cls.tm = ThreatModel.objects.create(name="Test TM", organization=cls.org)
        cls.component = OrgsystemComponent.objects.create(
            threat_model=cls.tm, name="Test Component"
        )
        cls.threat = ComponentInstanceThreat.objects.create(
            component=cls.component, inherent_severity="high"
        )

        cls.taxonomy = ExternalTaxonomy.objects.create(slug="stride", name="STRIDE")
        cls.entry_tampering = TaxonomyEntry.objects.create(
            taxonomy=cls.taxonomy, external_id="tampering", title="Tampering"
        )
        cls.entry_spoofing = TaxonomyEntry.objects.create(
            taxonomy=cls.taxonomy, external_id="spoofing", title="Spoofing"
        )

        cls.capec_taxonomy = ExternalTaxonomy.objects.create(slug="capec", name="CAPEC")
        cls.entry_capec_66 = TaxonomyEntry.objects.create(
            taxonomy=cls.capec_taxonomy, external_id="66", title="SQL Injection"
        )


class ModelConstraintTests(InstanceTaxonomyTestCase):
    """Test CheckConstraint and UniqueConstraint on InstanceThreatTaxonomyEntry."""

    def test_create_with_component_threat_succeeds(self):
        entry = InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_tampering,
            component_threat=self.threat,
        )
        self.assertEqual(entry.component_threat, self.threat)
        self.assertIsNone(entry.flow_threat)

    def test_create_with_neither_fk_fails(self):
        with self.assertRaises(IntegrityError):
            InstanceThreatTaxonomyEntry.objects.create(
                taxonomy_entry=self.entry_tampering,
            )

    def test_duplicate_taxonomy_entry_component_threat_fails(self):
        InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_tampering,
            component_threat=self.threat,
        )
        with self.assertRaises(IntegrityError):
            InstanceThreatTaxonomyEntry.objects.create(
                taxonomy_entry=self.entry_tampering,
                component_threat=self.threat,
            )

    def test_different_entries_same_threat_succeeds(self):
        InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_tampering,
            component_threat=self.threat,
        )
        entry2 = InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_spoofing,
            component_threat=self.threat,
        )
        self.assertIsNotNone(entry2.pk)


class APITests(InstanceTaxonomyTestCase):
    """Test the InstanceThreatTaxonomyEntryViewSet CRUD endpoints."""

    def setUp(self):
        self.client = APIClient()
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_entry(self):
        response = self.client.post(
            "/api/threat-taxonomy-entries/",
            {
                "taxonomyEntry": self.entry_tampering.pk,
                "componentThreat": self.threat.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["taxonomySlug"], "stride")
        self.assertEqual(data["externalId"], "tampering")
        self.assertEqual(data["title"], "Tampering")

    def test_list_filtered_by_component_threat(self):
        InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_tampering, component_threat=self.threat
        )
        InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_spoofing, component_threat=self.threat
        )
        response = self.client.get(
            f"/api/threat-taxonomy-entries/?component_threat={self.threat.pk}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get("results", data)
        self.assertEqual(len(results), 2)

    def test_delete_entry(self):
        entry = InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_tampering, component_threat=self.threat
        )
        response = self.client.delete(f"/api/threat-taxonomy-entries/{entry.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            InstanceThreatTaxonomyEntry.objects.filter(pk=entry.pk).exists()
        )

    def test_duplicate_returns_400(self):
        InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_tampering, component_threat=self.threat
        )
        response = self.client.post(
            "/api/threat-taxonomy-entries/",
            {
                "taxonomyEntry": self.entry_tampering.pk,
                "componentThreat": self.threat.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_requires_exactly_one_fk(self):
        response = self.client.post(
            "/api/threat-taxonomy-entries/",
            {"taxonomyEntry": self.entry_tampering.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_org_scoping(self):
        other_org = Organization.objects.create(name="Other Org", domain="other.org")
        other_user = User.objects.create_user(
            username="otheruser", email="other@other.org", password="testpass123"
        )
        OrganizationMember.objects.create(
            organization=other_org, user=other_user, role="security_team"
        )

        entry = InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_tampering, component_threat=self.threat
        )

        other_client = APIClient()
        other_token = str(RefreshToken.for_user(other_user).access_token)
        other_client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_token}")

        response = other_client.get(f"/api/threat-taxonomy-entries/{entry.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MergeLogicTests(InstanceTaxonomyTestCase):
    """Test that library + instance taxonomy entries merge correctly in views."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.library = ThreatLibrary.objects.create(
            name="SQL Injection", description="SQL injection threat"
        )
        cls.threat_with_library = ComponentInstanceThreat.objects.create(
            component=cls.component,
            threat_library=cls.library,
            inherent_severity="high",
        )
        ThreatLibraryTaxonomyEntry.objects.create(
            threat_library=cls.library,
            taxonomy_entry=cls.entry_tampering,
        )

    def setUp(self):
        self.client = APIClient()
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_instance_entry_adds_to_library_entries(self):
        InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_capec_66,
            component_threat=self.threat_with_library,
        )
        entries = InstanceThreatTaxonomyEntry.objects.filter(
            component_threat=self.threat_with_library
        )
        self.assertEqual(entries.count(), 1)
        library_entries = ThreatLibraryTaxonomyEntry.objects.filter(
            threat_library=self.library
        )
        self.assertEqual(library_entries.count(), 1)

    def test_instance_override_deduplicates_by_taxonomy_and_external_id(self):
        InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_tampering,
            component_threat=self.threat_with_library,
        )
        instance_count = InstanceThreatTaxonomyEntry.objects.filter(
            component_threat=self.threat_with_library
        ).count()
        library_count = ThreatLibraryTaxonomyEntry.objects.filter(
            threat_library=self.library
        ).count()
        self.assertEqual(instance_count, 1)
        self.assertEqual(library_count, 1)

    def test_custom_threat_only_has_instance_entries(self):
        custom_threat = ComponentInstanceThreat.objects.create(
            component=self.component, inherent_severity="medium"
        )
        InstanceThreatTaxonomyEntry.objects.create(
            taxonomy_entry=self.entry_spoofing,
            component_threat=custom_threat,
        )
        entries = InstanceThreatTaxonomyEntry.objects.filter(
            component_threat=custom_threat
        )
        self.assertEqual(entries.count(), 1)
        self.assertIsNone(custom_threat.threat_library)
