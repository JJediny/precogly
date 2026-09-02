"""The OAuth 2.1 authorization server an MCP client authenticates against.

Precogly issues the tokens; the MCP server validates them and holds no
credential of its own. A client reaches a token by discovering metadata,
registering itself, sending the user to a browser login, and exchanging the
returned code — so these tests walk that sequence rather than unit-testing
django-oauth-toolkit, which has its own suite.

What is pinned here is the configuration, because every failure this
configuration prevents is silent or intermittent: an authorize endpoint that
404s, a registration endpoint the metadata declines to advertise, a redirect
that works once and then stops.
"""

import base64
import hashlib
import json
import re
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from oauth2_provider.models import get_application_model, get_refresh_token_model
from oauth2_provider.settings import oauth2_settings

User = get_user_model()
Application = get_application_model()
RefreshToken = get_refresh_token_model()


def heading(response):
    """The text of the page's `h1`, with markup and attributes ignored.

    These assertions are about copy, which is what decision 0007 makes the
    mitigation. Matching a literal `<h1>Sign in</h1>` instead ties them to the
    markup: a restyle that adds a class breaks the positive assertion and, worse,
    makes the negative one pass against any page at all.
    """
    match = re.search(rb"<h1[^>]*>(.*?)</h1>", response.content, re.S)
    return match.group(1).decode().strip() if match else ""


REGISTERED_REDIRECT = "http://localhost:33418/callback"


def pkce_pair():
    """A PKCE verifier and its S256 challenge."""
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


class TestDiscovery(TestCase):
    """What a client reads before it can do anything else."""

    def test_the_metadata_points_at_the_prefixed_endpoints(self):
        # The document is served from the origin root because RFC 8414 puts it
        # there, while the endpoints it names live under /o/. Both mounts
        # describe the same views, so this catches a root mount that silently
        # advertises itself instead.
        document = self.client.get("/.well-known/oauth-authorization-server").json()

        assert document["authorization_endpoint"].endswith("/o/authorize/")
        assert document["token_endpoint"].endswith("/o/token/")
        assert document["introspection_endpoint"].endswith("/o/introspect/")

    def test_both_mounts_name_the_server_the_same_thing(self):
        # RFC 8414 makes `issuer` the server's identity and §3.3 compares it by exact
        # string, so the two mounts of this document cannot each name themselves.
        # Without OIDC_ISS_ENDPOINT they do: django-oauth-toolkit derives the issuer
        # from `request.path`, which gave "http://host" at the root and "http://host/o"
        # under the prefix.
        #
        # Latent while nothing sends a client to the prefixed copy — discovery runs
        # protected-resource document -> `authorization_servers` -> the root document.
        # It becomes a live failure the moment COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS
        # is set, because the `iss` parameter is built from the *prefixed* mount
        # (`oauth2_authorization_server_issuer` reverses the namespaced URL), so a
        # client that read the root document rejects its own authorization response
        # under RFC 9207 — the opposite of the mix-up defence that flag adds.
        root = self.client.get("/.well-known/oauth-authorization-server").json()
        prefixed = self.client.get("/o/.well-known/oauth-authorization-server").json()

        assert root["issuer"] == prefixed["issuer"]
        assert root["issuer"] == settings.MCP_ISSUER_URL

    def test_the_registration_endpoint_is_advertised(self):
        # Regression: the metadata view gates this on DCR_ENABLED rather than on
        # the URL resolving, and DCR_ENABLED is off by default. With it off,
        # /o/register/ answers but no client ever learns the address, so
        # discovery completes and connection fails with nothing to point at.
        document = self.client.get("/.well-known/oauth-authorization-server").json()

        assert document["registration_endpoint"].endswith("/o/register/")

    def test_neither_plain_pkce_nor_the_credential_grants_are_offered(self):
        # RFC 9700 hardening, enforced in oauth2_validators rather than only
        # described here. A server that advertises the password grant invites a
        # client to ask for one, and the point of this design is that no client
        # ever handles a user's credential.
        document = self.client.get("/.well-known/oauth-authorization-server").json()

        assert document["code_challenge_methods_supported"] == ["S256"]
        assert "password" not in document["grant_types_supported"]
        assert "implicit" not in document["grant_types_supported"]

    def test_django_does_not_answer_for_a_protected_resource(self):
        # django-oauth-toolkit publishes RFC 9728 metadata too, and config.urls leaves
        # those two patterns out on purpose. The only protected resource here is /mcp,
        # which publishes its own document out of the same AuthSettings its token
        # verifier enforces. Routed as well, Django answered the same path from
        # OAUTH2_PROVIDER["SCOPES"] — advertising `write` for an endpoint with no write
        # tool — and the dispatch order in config.wsgi decided which one a client saw.
        #
        # 404 here rather than at the endpoint: the MCP app is dispatched to before
        # Django, so a request that arrives at the URLconf at all has already missed it.
        assert (
            self.client.get("/.well-known/oauth-protected-resource").status_code == 404
        )
        assert (
            self.client.get("/.well-known/oauth-protected-resource/mcp").status_code
            == 404
        )


class TestTheLoginTheAuthorizeViewNeeds(TestCase):
    """django-oauth-toolkit redirects to LOGIN_URL; something has to be there."""

    def test_the_login_url_resolves(self):
        # Regression: Django's default LOGIN_URL is /accounts/login/ and this
        # project routed nothing under /accounts/, so an unauthenticated
        # authorize request redirected to a 404. allauth is installed but its
        # URLs were never included.
        try:
            resolve("/accounts/login/")
        except Resolver404 as err:  # pragma: no cover - what this test exists for
            raise AssertionError(
                "/accounts/login/ does not resolve, so the authorize view "
                "redirects an unauthenticated user to a 404"
            ) from err

        assert self.client.get("/accounts/login/").status_code == 200

    def test_an_unauthenticated_authorize_request_lands_on_that_login(self):
        response = self.client.get(reverse("oauth2_provider:authorize"))

        assert response.status_code == 302
        assert response.headers["Location"].startswith("/accounts/login/")


class TestDynamicClientRegistration(TestCase):
    """A client registers itself before any browser has opened."""

    def register(self, **overrides):
        body = {
            "client_name": "Claude Code",
            "redirect_uris": [REGISTERED_REDIRECT],
            "grant_types": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_method": "none",
            **overrides,
        }
        return self.client.post(
            reverse("oauth2_provider:dcr-register"),
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_a_client_registers_without_a_session(self):
        # The default permission class wants a session-authenticated user, which
        # no MCP client has at this point in the flow — it registers before the
        # user is sent anywhere. With the default in place every client is
        # refused at its first write.
        response = self.register()

        assert response.status_code == 201
        assert response.json()["client_id"]

    def test_a_registered_client_may_return_to_another_loopback_port(self):
        # Regression, and the reason ALLOW_LOCALHOST_LOOPBACK is set: RFC 8252
        # exempts loopback redirects from port matching because a native client
        # binds whatever port is free, but django-oauth-toolkit withholds that
        # exemption from the hostname "localhost" by default. Clients spell it
        # "localhost" anyway. Without the setting this passes on the port the
        # client happened to register and fails on every other one, which reads
        # as an intermittent redirect_uri mismatch.
        application = Application.objects.get(
            client_id=self.register().json()["client_id"]
        )

        assert application.redirect_uri_allowed("http://localhost:51999/callback")

    @override_settings(OAUTH2_PROVIDER={"ALLOW_LOCALHOST_LOOPBACK": False})
    def test_without_the_loopback_exemption_a_changed_port_is_refused(self):
        # The negative half of the test above. It documents that the setting is
        # load-bearing rather than defensive: remove it and this is the
        # behaviour a client meets.
        application = Application.objects.create(
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=REGISTERED_REDIRECT,
        )

        assert not application.redirect_uri_allowed("http://localhost:51999/callback")


class TestTheScreensTheUserSees(TestCase):
    """The two server-rendered pages, and the fields they must not drop."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="screens", email="screens@test.org", password="testpass123"
        )

    def test_the_login_page_keeps_the_return_journey(self):
        # Regression risk in overriding allauth's template: allauth renders the
        # `next` parameter through {{ redirect_field }}, and a hand-written form
        # that omits it signs the user in and drops them on the site root, part
        # way through an authorization they then have to restart.
        response = self.client.get("/accounts/login/", {"next": "/o/authorize/?x=1"})

        assert "account/login.html" in [t.name for t in response.templates]
        self.assertContains(response, 'name="next"')
        self.assertContains(response, "/o/authorize/")

    def test_the_login_page_says_why_it_is_asking_again(self):
        # Almost everyone reaching this page is already signed in — the React
        # app is the normal way in and holds a JWT, not a session — so a bare
        # "Sign in" reads as the site having forgotten them. Re-authenticating
        # before an agent gets standing access is deliberate, and this copy is
        # the whole of what makes that legible. Pinned because a template tidy
        # would otherwise silently turn a decision back into an accident.
        response = self.client.get(
            "/accounts/login/", {"next": "/o/authorize/?client_id=abc"}
        )

        assert heading(response) == "Confirm it's you"

    def test_a_plain_visit_still_just_says_sign_in(self):
        # The re-authentication framing belongs to the authorization flow. Any
        # other arrival is an ordinary login and should not be told it is about
        # to grant something.
        response = self.client.get("/accounts/login/")

        assert heading(response) == "Sign in"
        self.assertNotContains(response, "Confirm it's you")

    def test_the_consent_screen_offers_a_button_named_allow(self):
        # `name="allow"` is the only thing separating approval from
        # cancellation — both are submits on the same form. A restyle that
        # renames it turns every Authorize click into a denial.
        self.client.force_login(self.user)
        application = Application.objects.create(
            name="Claude Code",
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=REGISTERED_REDIRECT,
        )
        _, challenge = pkce_pair()

        response = self.client.get(
            reverse("oauth2_provider:authorize"),
            {
                "response_type": "code",
                "client_id": application.client_id,
                "redirect_uri": REGISTERED_REDIRECT,
                "scope": "read",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )

        assert "oauth2_provider/authorize.html" in [t.name for t in response.templates]
        self.assertContains(response, 'name="allow"')
        # The scope sentence comes from settings, so a user reads what we wrote.
        self.assertContains(response, "Read your threat models")


class TestSigningInDuringAuthorization(TestCase):
    """The leg every other test here skips by forcing a session.

    `force_login` sets the session cookie directly, so it proves nothing about
    whether a person can sign in and be returned to where they were going. That
    is the whole reason this flow needed a browser login in the first place, so
    it is walked here with real credentials and no shortcut.
    """

    @classmethod
    def setUpTestData(cls):
        cls.password = "testpass123"
        cls.user = User.objects.create_user(
            username="walker", email="walker@test.org", password=cls.password
        )
        cls.application = Application.objects.create(
            name="Claude Code",
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=REGISTERED_REDIRECT,
        )

    def test_an_anonymous_user_signs_in_and_lands_back_on_consent(self):
        _, challenge = pkce_pair()
        authorize_url = (
            f"{reverse('oauth2_provider:authorize')}?response_type=code"
            f"&client_id={self.application.client_id}"
            f"&redirect_uri={REGISTERED_REDIRECT}&scope=read"
            f"&code_challenge={challenge}&code_challenge_method=S256"
        )

        # 1. Arrive with no session and get sent to the login page.
        bounced = self.client.get(authorize_url)
        assert bounced.status_code == 302
        login_url = bounced.headers["Location"]
        assert login_url.startswith("/accounts/login/")

        # 2. Sign in, for real, against the form that page renders. allauth
        #    names the identifier field "login" and this project logs in by
        #    email, so an email goes in it.
        signed_in = self.client.post(
            login_url,
            {"login": self.user.email, "password": self.password},
            follow=True,
        )

        # 3. Land back on the consent screen rather than on the site root. This
        #    is what {{ redirect_field }} in the login template buys; without it
        #    the user authenticates and the authorization is silently abandoned.
        assert signed_in.status_code == 200
        assert "oauth2_provider/authorize.html" in [t.name for t in signed_in.templates]
        self.assertContains(signed_in, 'name="allow"')
        assert signed_in.redirect_chain[-1][0].startswith(
            reverse("oauth2_provider:authorize")
        )

    def test_bad_credentials_do_not_authorize_anything(self):
        _, challenge = pkce_pair()
        authorize_url = (
            f"{reverse('oauth2_provider:authorize')}?response_type=code"
            f"&client_id={self.application.client_id}"
            f"&redirect_uri={REGISTERED_REDIRECT}&scope=read"
            f"&code_challenge={challenge}&code_challenge_method=S256"
        )
        login_url = self.client.get(authorize_url).headers["Location"]

        response = self.client.post(
            login_url,
            {"login": self.user.email, "password": "wrong-password"},
            follow=True,
        )

        assert "account/login.html" in [t.name for t in response.templates]
        assert "_auth_user_id" not in self.client.session


class TestTheGrant(TestCase):
    """Login, consent, code, token — the sequence a user actually walks."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="mcpuser", email="mcp@test.org", password="testpass123"
        )

    def setUp(self):
        self.client.force_login(self.user)
        registration = self.client.post(
            reverse("oauth2_provider:dcr-register"),
            data=json.dumps(
                {
                    "client_name": "Claude Code",
                    "redirect_uris": [REGISTERED_REDIRECT],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "token_endpoint_auth_method": "none",
                }
            ),
            content_type="application/json",
        ).json()
        self.client_id = registration["client_id"]
        self.verifier, self.challenge = pkce_pair()

    def authorize_params(self, **overrides):
        return {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": REGISTERED_REDIRECT,
            "scope": "read",
            "state": "opaque-state",
            "code_challenge": self.challenge,
            "code_challenge_method": "S256",
            **overrides,
        }

    def test_a_consenting_user_gets_a_token_that_is_opaque(self):
        # Opaque rather than self-contained is the decision the MCP server's
        # introspection contract rests on: the token carries no claims, so
        # revoking it takes effect on the next request rather than at expiry.
        self.client.get(reverse("oauth2_provider:authorize"), self.authorize_params())
        consent = self.client.post(
            reverse("oauth2_provider:authorize"),
            {**self.authorize_params(), "allow": "Authorize"},
        )
        code = parse_qs(urlparse(consent.headers["Location"]).query)["code"][0]

        response = self.client.post(
            reverse("oauth2_provider:token"),
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REGISTERED_REDIRECT,
                "client_id": self.client_id,
                "code_verifier": self.verifier,
            },
        )

        assert response.status_code == 200
        token = response.json()
        assert token["token_type"] == "Bearer"
        assert token["scope"] == "read"
        assert "refresh_token" in token
        assert "." not in token["access_token"], "expected an opaque token, not a JWT"

    def test_the_code_is_useless_without_the_verifier(self):
        # PKCE is what stops an intercepted code being redeemed. The client is
        # public and holds no secret, so this is the only thing binding the code
        # to whoever started the flow.
        self.client.get(reverse("oauth2_provider:authorize"), self.authorize_params())
        consent = self.client.post(
            reverse("oauth2_provider:authorize"),
            {**self.authorize_params(), "allow": "Authorize"},
        )
        code = parse_qs(urlparse(consent.headers["Location"]).query)["code"][0]

        response = self.client.post(
            reverse("oauth2_provider:token"),
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REGISTERED_REDIRECT,
                "client_id": self.client_id,
                "code_verifier": secrets.token_urlsafe(64),
            },
        )

        assert response.status_code == 400


class TestRefreshTokenRotation(TestCase):
    """What happens when a refresh token is presented twice.

    RFC 9700 §4.14.2 defines rotation as invalidating the presented token *and*
    revoking the active one once a replay proves two parties hold it: "the
    authorization server cannot determine which party submitted the invalid refresh
    token, but it will revoke the active refresh token." Rotation alone does only the
    first half, which leaves a stolen token outliving the client it was taken from.

    The grace window is what separates a breach from a client that retried after its
    connection dropped once the server had committed the rotation. Both cases are
    covered here, because enabling replay detection without the window turns the
    second into the first.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="rotator", email="rotate@test.org", password="testpass123"
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.client_id = self.client.post(
            reverse("oauth2_provider:dcr-register"),
            data=json.dumps(
                {
                    "client_name": "Claude Code",
                    "redirect_uris": [REGISTERED_REDIRECT],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "token_endpoint_auth_method": "none",
                }
            ),
            content_type="application/json",
        ).json()["client_id"]
        self.verifier, self.challenge = pkce_pair()

    def first_refresh_token(self):
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": REGISTERED_REDIRECT,
            "scope": "read",
            "state": "opaque-state",
            "code_challenge": self.challenge,
            "code_challenge_method": "S256",
        }
        self.client.get(reverse("oauth2_provider:authorize"), params)
        consent = self.client.post(
            reverse("oauth2_provider:authorize"), {**params, "allow": "Authorize"}
        )
        code = parse_qs(urlparse(consent.headers["Location"]).query)["code"][0]
        return self.client.post(
            reverse("oauth2_provider:token"),
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REGISTERED_REDIRECT,
                "client_id": self.client_id,
                "code_verifier": self.verifier,
            },
        ).json()["refresh_token"]

    def refresh(self, token):
        return self.client.post(
            reverse("oauth2_provider:token"),
            {
                "grant_type": "refresh_token",
                "refresh_token": token,
                "client_id": self.client_id,
            },
        )

    def age_out_of_grace(self, token):
        """Back-date the rotation so the grace window has passed.

        Sleeping the window instead would put REFRESH_TOKEN_GRACE_PERIOD_SECONDS of
        real time in the suite, and rewriting `revoked` reaches the same branch:
        `validate_refresh_token` compares it against `now - grace`.
        """
        row = RefreshToken.objects.get(
            token_checksum=hashlib.sha256(token.encode()).hexdigest()
        )
        row.revoked = timezone.now() - timedelta(
            seconds=oauth2_settings.REFRESH_TOKEN_GRACE_PERIOD_SECONDS + 1
        )
        row.save(update_fields=["revoked"])

    def test_a_replayed_token_takes_the_whole_family_with_it(self):
        first = self.first_refresh_token()
        second = self.refresh(first).json()["refresh_token"]
        self.age_out_of_grace(first)

        replayed = self.refresh(first)

        assert replayed.status_code == 400
        assert replayed.json()["error"] == "invalid_grant"
        # The half REFRESH_TOKEN_REUSE_PROTECTION adds. Without it this token keeps
        # working, so a thief who replayed the old one is refused once and continues
        # from the chain they already hold.
        assert self.refresh(second).status_code == 400

    def test_a_retry_inside_the_grace_window_is_not_treated_as_a_breach(self):
        # The reason the grace period cannot be left at 0 alongside replay detection:
        # a client whose connection dropped after the server committed the rotation
        # replays in good faith, and revoking its family would cost a user their
        # session over a lost packet. Inside the window it is handed the pair the
        # rotation already minted.
        first = self.first_refresh_token()
        second = self.refresh(first).json()["refresh_token"]

        retried = self.refresh(first)

        assert retried.status_code == 200
        assert self.refresh(second).status_code == 200
