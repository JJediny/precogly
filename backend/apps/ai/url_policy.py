"""Policy for which addresses a model endpoint may resolve to.

An organization sets :attr:`AIProviderConfig.base_url` through the settings UI and
Precogly fetches it server-side. Unchecked, that makes the form a way to send a
request from inside the deployment's network — including to the host Precogly
runs on, which no firewall or egress rule can prevent.

Users with freshly minted accounts can exploit this in a production environment:
signup is routed unconditionally (``config/urls.py``), ``ACCOUNT_EMAIL_VERIFICATION``
is ``"optional"``, and ``apps.organizations.signals`` auto-joins uninvited new
users to the primary organization (intended; see ``docs/concepts/org-hierarchy.md``).
Saving a config needs membership and no particular role. So anyone who can
register can reach this.

``AI_PROVIDER_URL_POLICY`` selects which addresses pass, defaulted per settings
module; see ``config/settings/production.py``.

# Trade-offs

The hostname is resolved here and again by ``requests`` when it connects, so a
name that answers differently across those two moments — DNS rebinding — defeats
this. Closing it means pinning the checked address for the connection: a custom
``requests`` transport adapter, plus SNI and certificate handling for TLS.

Redirects would defeat it the same way, and are closed: callers pass
``allow_redirects=False``.
"""

import socket
from ipaddress import IPv6Address, ip_address
from urllib.parse import urlsplit

from django.conf import settings

DENY_PRIVATE = "deny-private"
ALLOW_LOOPBACK = "allow-loopback"

POLICIES = (DENY_PRIVATE, ALLOW_LOOPBACK)


class URLPolicyError(ValueError):
    """A model endpoint URL is not permitted by this deployment's policy.

    A ``ValueError`` so a DRF serializer's ``validate_*`` hook can let it
    surface as a 400 against the field, while the request-time callers catch it
    explicitly.
    """


def current_policy() -> str:
    """The configured policy, falling back to the strict one.

    An unrecognised value fails closed rather than raising at request time: a
    typo in a deployment's environment should cost that deployment its loopback
    provider, not turn the check off.
    """
    configured = getattr(settings, "AI_PROVIDER_URL_POLICY", DENY_PRIVATE)
    return configured if configured in POLICIES else DENY_PRIVATE


def check_url(raw_url: str, *, policy: str | None = None) -> None:
    """Raise :class:`URLPolicyError` unless ``raw_url`` may be fetched.

    Every address the hostname resolves to has to pass, not just the first.
    A name with both a public and a private answer is a bypass if only one is
    checked, and which one ``requests`` picks is not ours to decide.
    """
    policy = policy or current_policy()
    parts = urlsplit(raw_url)

    if parts.scheme not in ("http", "https"):
        raise URLPolicyError(
            f"Model endpoints must use http or https, not '{parts.scheme}'."
        )

    hostname = parts.hostname
    if not hostname:
        raise URLPolicyError("Model endpoint URL has no host.")

    for resolved in _resolve(hostname):
        if not _is_permitted(resolved, policy):
            raise URLPolicyError(_rejection(hostname, resolved, policy))


def _resolve(hostname: str) -> list:
    """Every IP the hostname answers with, as :mod:`ipaddress` objects.

    A literal address parses without a lookup — ``getaddrinfo`` would return it
    unchanged, but only after a syscall that can block.
    """
    try:
        return [ip_address(hostname)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as err:
        raise URLPolicyError(
            f"Could not resolve '{hostname}'. Check the base URL is spelled "
            "correctly and the host exists."
        ) from err

    return [ip_address(info[4][0]) for info in infos]


def _is_permitted(ip, policy: str) -> bool:
    """Whether one resolved address may be connected to under ``policy``."""
    # ::ffff:127.0.0.1 is loopback wearing an IPv6 shape. Judging it as IPv6
    # would call it neither loopback nor global, making it rejected under
    # allow-loopback for the wrong reason.
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    if ip.is_loopback:
        return policy == ALLOW_LOOPBACK

    # is_global is false for private, link-local, multicast, reserved,
    # unspecified, and the shared CGNAT range — every category we would
    # otherwise have to enumerate and keep in step with IANA.
    return ip.is_global


def _rejection(hostname: str, ip, policy: str) -> str:
    """Properly explain why the hostname got rejected."""
    where = f"'{hostname}'" if str(ip) == hostname else f"'{hostname}' ({ip})"

    if ip.is_loopback:
        return (
            f"{where} is a loopback address, which this deployment does not "
            f"allow for model endpoints. Set AI_PROVIDER_URL_POLICY to "
            f"'{ALLOW_LOOPBACK}' if the model runs on the same host as Precogly."
        )
    return (
        f"{where} is not a publicly routable address, so it cannot be used as a "
        f"model endpoint. Private, link-local, and reserved ranges are refused "
        f"under every policy setting."
    )
