"""Tests for the outbound-URL policy on tenant-supplied model endpoints.

Two layers, because the policy has two jobs. The first set drives
:func:`apps.ai.url_policy.check_url` directly and is about *which* addresses are
refused — the cases that matter are the ones a naive string check would miss:
a hostname that resolves into a private range, a hostname with one public and
one private answer, and the cloud metadata address, which has to stay refused
even on the permissive setting.

The second set is about *where* the check runs. It belongs immediately before
each request rather than only at save time, and it must not fire on the
operator-wide fallback, which is the deployment's own setting and ships pointing
at loopback.

DNS is mocked throughout. A test that resolved real names would be measuring the
network.
"""

import socket
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai import url_policy
from apps.ai.models import AIProviderConfig
from apps.ai.providers import openai_compat
from apps.ai.providers.base import AIProviderError, ResolvedConfig
from apps.ai.providers.openai_compat import OpenAICompatProvider
from apps.ai.url_policy import ALLOW_LOOPBACK, DENY_PRIVATE, URLPolicyError, check_url
from apps.organizations.models import Organization, OrganizationMember

User = get_user_model()

# 169.254.169.254 is the link-local address that AWS, GCP, and Azure all serve
# instance credentials from. It is the reason this module exists, so it gets a
# name rather than appearing as a bare literal in one assertion.
CLOUD_METADATA = "169.254.169.254"


def _addrinfo(*ips):
    """A ``getaddrinfo`` return value carrying ``ips``.

    Only element 4, the sockaddr, is read by the code under test; the rest is
    filled in so the shape matches what the real call returns.
    """
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips]


class AddressDecisionTests(SimpleTestCase):
    """Which addresses each policy admits, checked on literals — no DNS."""

    def test_public_address_allowed_under_both_policies(self):
        for policy in (DENY_PRIVATE, ALLOW_LOOPBACK):
            with self.subTest(policy=policy):
                check_url("https://93.184.216.34/v1", policy=policy)

    def test_loopback_refused_under_deny_private(self):
        with self.assertRaises(URLPolicyError) as caught:
            check_url("http://127.0.0.1:1234/v1", policy=DENY_PRIVATE)
        # The message has to name the escape hatch, or a self-hoster whose local
        # model stopped working has no way to find out why.
        self.assertIn(ALLOW_LOOPBACK, str(caught.exception))

    def test_loopback_allowed_under_allow_loopback(self):
        check_url("http://127.0.0.1:1234/v1", policy=ALLOW_LOOPBACK)

    def test_metadata_address_refused_under_every_policy(self):
        # allow-loopback exists so a self-hoster can reach a model on the same
        # box. That is 127.0.0.0/8. It must not become a way to reach the
        # instance's credentials.
        for policy in (DENY_PRIVATE, ALLOW_LOOPBACK):
            with self.subTest(policy=policy), self.assertRaises(URLPolicyError):
                check_url(f"http://{CLOUD_METADATA}/latest/meta-data/", policy=policy)

    def test_private_range_refused_under_allow_loopback(self):
        with self.assertRaises(URLPolicyError):
            check_url("http://10.0.0.5:8000/v1", policy=ALLOW_LOOPBACK)

    def test_ipv4_mapped_loopback_is_treated_as_loopback(self):
        # ::ffff:127.0.0.1 is loopback in an IPv6 shape. Judged as plain IPv6 it
        # is neither loopback nor global, so it would be refused even under
        # allow-loopback — right answer, wrong reason, and the message would
        # tell the operator to set a policy that is already set.
        check_url("http://[::ffff:127.0.0.1]:1234/v1", policy=ALLOW_LOOPBACK)
        with self.assertRaises(URLPolicyError):
            check_url("http://[::ffff:127.0.0.1]:1234/v1", policy=DENY_PRIVATE)

    def test_non_http_scheme_refused(self):
        for url in (
            "file:///etc/passwd",
            "gopher://example.com/",
            "ftp://example.com/",
        ):
            with self.subTest(url=url), self.assertRaises(URLPolicyError):
                check_url(url, policy=DENY_PRIVATE)

    def test_url_without_host_refused(self):
        with self.assertRaises(URLPolicyError):
            check_url("http:///v1", policy=DENY_PRIVATE)


class ResolutionTests(SimpleTestCase):
    """What the policy does with names, which is where a string check fails."""

    @mock.patch.object(url_policy.socket, "getaddrinfo")
    def test_hostname_resolving_into_private_range_is_refused(self, getaddrinfo):
        getaddrinfo.return_value = _addrinfo("10.0.0.5")
        with self.assertRaises(URLPolicyError) as caught:
            check_url("http://internal.example.com/v1", policy=DENY_PRIVATE)
        # Both halves belong in the message: the name the operator typed, and
        # the address that actually caused the refusal.
        self.assertIn("internal.example.com", str(caught.exception))
        self.assertIn("10.0.0.5", str(caught.exception))

    @mock.patch.object(url_policy.socket, "getaddrinfo")
    def test_every_resolved_address_must_pass(self, getaddrinfo):
        # A name answering with one public and one private address is a bypass
        # if only the first answer is checked, and which one `requests` picks
        # when it connects is not ours to choose.
        getaddrinfo.return_value = _addrinfo("93.184.216.34", CLOUD_METADATA)
        with self.assertRaises(URLPolicyError):
            check_url("http://split-horizon.example.com/v1", policy=DENY_PRIVATE)

    @mock.patch.object(url_policy.socket, "getaddrinfo")
    def test_public_hostname_allowed(self, getaddrinfo):
        getaddrinfo.return_value = _addrinfo("93.184.216.34")
        check_url("https://api.example.com/v1", policy=DENY_PRIVATE)

    @mock.patch.object(url_policy.socket, "getaddrinfo")
    def test_unresolvable_host_is_refused_with_an_actionable_message(self, getaddrinfo):
        getaddrinfo.side_effect = socket.gaierror("nope")
        with self.assertRaises(URLPolicyError) as caught:
            check_url("http://nx.example.invalid/v1", policy=DENY_PRIVATE)
        self.assertIn("resolve", str(caught.exception).lower())

    @mock.patch.object(url_policy.socket, "getaddrinfo")
    def test_literal_address_skips_the_lookup(self, getaddrinfo):
        check_url("https://93.184.216.34/v1", policy=DENY_PRIVATE)
        getaddrinfo.assert_not_called()


class PolicySelectionTests(SimpleTestCase):
    """How the configured value is read, including when it is wrong."""

    @override_settings(AI_PROVIDER_URL_POLICY=ALLOW_LOOPBACK)
    def test_configured_policy_is_used(self):
        self.assertEqual(url_policy.current_policy(), ALLOW_LOOPBACK)
        check_url("http://127.0.0.1:1234/v1")

    @override_settings(AI_PROVIDER_URL_POLICY="allow-everything")
    def test_unrecognised_policy_fails_closed(self):
        # A typo in a deployment's environment should cost that deployment its
        # loopback provider, not silently turn the check off.
        self.assertEqual(url_policy.current_policy(), DENY_PRIVATE)
        with self.assertRaises(URLPolicyError):
            check_url("http://127.0.0.1:1234/v1")


def _response(status_code=200, json_body=None):
    resp = mock.Mock(spec=["status_code", "json", "text"])
    resp.status_code = status_code
    resp.text = ""
    if json_body is None:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = json_body
    return resp


def _tenant_config(base_url):
    """A config as it arrives from an org's saved row: it carries a config_id."""
    return ResolvedConfig(
        provider_type="openai_compat",
        base_url=base_url,
        model="local-model",
        request_timeout=5,
        config_id=42,
    )


def _operator_config(base_url):
    """The settings fallback: no config_id, so the policy does not apply."""
    return ResolvedConfig(
        provider_type="openai_compat",
        base_url=base_url,
        model="local-model",
        request_timeout=5,
    )


@override_settings(AI_PROVIDER_URL_POLICY=DENY_PRIVATE)
class ProviderEnforcementTests(SimpleTestCase):
    """That the check runs before the request, and on the right configs."""

    @mock.patch.object(openai_compat.requests, "get")
    def test_probe_of_blocked_tenant_url_makes_no_request(self, get):
        health = OpenAICompatProvider(
            _tenant_config("http://127.0.0.1:1234/v1")
        ).test_connection()

        self.assertFalse(health.ok)
        # The point of the whole change: not merely that the caller is told no,
        # but that nothing left the process.
        get.assert_not_called()

    @mock.patch.object(openai_compat.requests, "post")
    def test_completion_against_blocked_tenant_url_makes_no_request(self, post):
        provider = OpenAICompatProvider(_tenant_config(f"http://{CLOUD_METADATA}/v1"))
        with self.assertRaises(AIProviderError):
            provider.complete([{"role": "user", "content": "hi"}])
        post.assert_not_called()

    @mock.patch.object(openai_compat.requests, "get")
    def test_operator_fallback_is_checked_too(self, get):
        # One rule, both sources. The fallback comes from the same environment
        # as the policy, so exempting it would have been defensible — but it
        # does nothing until AI_SUGGESTIONS_ENABLED is on, so there is no
        # shipped default that a uniform rule breaks.
        health = OpenAICompatProvider(
            _operator_config("http://127.0.0.1:1234/v1")
        ).test_connection()

        self.assertFalse(health.ok)
        get.assert_not_called()

    @mock.patch.object(openai_compat.requests, "get")
    def test_probe_does_not_follow_redirects(self, get):
        # A permitted host answering 302 Location: http://169.254.169.254/ would
        # defeat a check made on the original URL, so the redirect must not be
        # followed. This is the other half of the fix; neither half covers the
        # other's case.
        get.return_value = _response(json_body={"data": []})
        OpenAICompatProvider(
            _tenant_config("https://93.184.216.34/v1")
        ).test_connection()
        self.assertIs(get.call_args.kwargs["allow_redirects"], False)

    @mock.patch.object(openai_compat.requests, "post")
    def test_completion_does_not_follow_redirects(self, post):
        post.return_value = _response(
            json_body={"choices": [{"message": {"content": "hi"}}]}
        )
        OpenAICompatProvider(_tenant_config("https://93.184.216.34/v1")).complete(
            [{"role": "user", "content": "hi"}]
        )
        self.assertIs(post.call_args.kwargs["allow_redirects"], False)


@override_settings(
    AI_SECRET_KEY="policy-test-secret", AI_PROVIDER_URL_POLICY=DENY_PRIVATE
)
class ProviderConfigAPIPolicyTests(APITestCase):
    """The refusal as a client sees it, through auth, serializer, and viewset.

    The unit tests above prove the policy decides correctly and that the adapter
    consults it. This proves the two are actually wired to each other on the path
    a request takes, which is the only claim that matters to someone reproducing
    the original finding.
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Acme")
        cls.member = User.objects.create_user(
            username="member", email="member@acme.test", password="pw"
        )
        OrganizationMember.objects.create(organization=cls.org, user=cls.member)

    def setUp(self):
        self.client.force_authenticate(self.member)

    def _payload(self, base_url):
        return {
            "organization": self.org.id,
            "name": "Probe",
            "providerType": "openai_compat",
            "baseUrl": base_url,
            "model": "local-model",
        }

    def test_metadata_endpoint_is_rejected_on_create(self):
        response = self.client.post(
            "/api/ai-providers/",
            self._payload(f"http://{CLOUD_METADATA}/latest/meta-data/"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # `response.data` is pre-render, so the key is still snake_case here;
        # djangorestframework-camel-case rewrites it on the way out.
        self.assertIn("base_url", response.data)
        self.assertEqual(AIProviderConfig.objects.count(), 0)

    def test_probe_of_a_config_that_predates_the_policy_is_refused(self):
        # The serializer cannot be the only check: this row was written before
        # the policy existed, or by a name that resolved publicly at the time.
        # Saving is bypassed here deliberately to reproduce that state.
        config = AIProviderConfig.objects.create(
            organization=self.org,
            name="Legacy",
            base_url=f"http://{CLOUD_METADATA}/latest/meta-data/",
            model="local-model",
        )

        with mock.patch.object(openai_compat.requests, "get") as get:
            response = self.client.post(
                f"/api/ai-providers/{config.id}/test-connection/", format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["ok"])
        get.assert_not_called()
