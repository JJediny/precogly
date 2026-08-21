"""API regression tests for data assets linked to data flows."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.organizations.models import Organization, OrganizationMember
from apps.systems.models import DataAsset, DataFlow, DataFlowAsset, OrgsystemComponent
from apps.threat_models.models import ThreatModel

User = get_user_model()


class DataFlowAssetAPITests(APITestCase):
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

    def setUp(self):
        self.client.force_authenticate(self.member)

    @staticmethod
    def _flow(threat_model, label):
        source = OrgsystemComponent.objects.create(
            name=f"{label} source", threat_model=threat_model
        )
        destination = OrgsystemComponent.objects.create(
            name=f"{label} destination", threat_model=threat_model
        )
        return DataFlow.objects.create(
            source_component=source,
            dest_component=destination,
            label=label,
        )

    def test_created_asset_link_is_returned_for_threat_model_components(self):
        flow = self._flow(self.threat_model, "Acme flow")
        asset = DataAsset.objects.create(
            threat_model=self.threat_model,
            name="Customer records",
            classification="confidential",
        )

        create_response = self.client.post(
            "/api/data-flow-assets/",
            {"dataFlow": flow.id, "dataAsset": asset.id, "protectionMethod": "none"},
            format="json",
        )
        self.assertEqual(
            create_response.status_code, status.HTTP_201_CREATED, create_response.data
        )

        list_response = self.client.get(
            "/api/data-flow-assets/", {"data_flow": flow.id}
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["data_asset"], asset.id)

    def test_asset_links_from_other_organizations_are_not_returned(self):
        flow = self._flow(self.other_threat_model, "Globex flow")
        asset = DataAsset.objects.create(
            threat_model=self.other_threat_model,
            name="Private records",
            classification="confidential",
        )
        DataFlowAsset.objects.create(data_flow=flow, data_asset=asset)

        response = self.client.get("/api/data-flow-assets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
