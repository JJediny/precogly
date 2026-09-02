"""Per-tenant "bring your own model" configuration.

An :class:`AIProviderConfig` is one organization's saved model endpoint: which
provider, which URL/model, and an encrypted API key. The resolver
(:mod:`apps.ai.resolver`) picks the org's enabled default before falling back to
the operator-wide ``AI_*`` settings, so orgs that configure their own model
override the deployment default without code changes.

The API key is encrypted on the way in and decrypted on the way out; callers use
:meth:`set_api_key` and the :attr:`api_key` property and never see ciphertext.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel
from apps.core.tenancy import Tenancy

from .crypto import decrypt, encrypt
from .providers.base import ResolvedConfig


class AIProviderConfig(TimestampedModel):
    """An organization's configuration for one AI model endpoint."""

    tenancy = Tenancy.TENANT_OWNED

    class ProviderType(models.TextChoices):
        # Only OpenAI-compatible endpoints are supported today. New, non-
        # compatible providers add a value here *and* an adapter in
        # apps.ai.providers.registry — the model itself doesn't need to change
        # beyond this list.
        OPENAI_COMPAT = "openai_compat", "OpenAI-compatible"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="ai_provider_configs",
    )
    name = models.CharField(
        max_length=255,
        help_text="Operator-facing label, e.g. 'Local LM Studio' or 'Team OpenAI'.",
    )
    provider_type = models.CharField(
        max_length=32,
        choices=ProviderType.choices,
        default=ProviderType.OPENAI_COMPAT,
    )
    base_url = models.URLField(
        help_text="OpenAI-style root exposing /chat/completions, e.g. "
        "http://localhost:1234/v1.",
    )
    model = models.CharField(
        max_length=255,
        help_text="Model name/identifier the endpoint expects.",
    )
    # Encrypted at rest via apps.ai.crypto; never read or written directly.
    # Blank means the endpoint needs no auth (typical for local servers).
    api_key_encrypted = models.TextField(blank=True, default="")
    request_timeout = models.PositiveIntegerField(
        default=60,
        help_text="Seconds to wait for the model before failing with an error.",
    )
    # The org's selected provider. The resolver uses the default; others are
    # kept as ready-to-switch alternatives.
    is_default = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["organization_id", "name"]
        constraints = [
            # A given label is unique within an org so configs are unambiguous.
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_ai_provider_name_per_org",
            ),
            # At most one default config per organization, enforced in the DB so
            # the resolver can trust there is never an ambiguous default.
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(is_default=True),
                name="unique_default_ai_provider_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_provider_type_display()})"

    def set_api_key(self, raw: str) -> None:
        """Encrypt and store an API key. Pass an empty string to clear it."""
        self.api_key_encrypted = encrypt(raw or "")

    @property
    def api_key(self) -> str:
        """The decrypted API key (empty when none is set)."""
        return decrypt(self.api_key_encrypted)

    def to_resolved_config(self) -> ResolvedConfig:
        """Flatten into the decrypted snapshot adapters consume."""
        return ResolvedConfig(
            provider_type=self.provider_type,
            base_url=self.base_url,
            model=self.model,
            api_key=self.api_key,
            request_timeout=self.request_timeout,
            config_id=self.id,
        )


class AIUsageRecord(TimestampedModel):
    """One AI call's token usage (and cost, when the provider is priced).

    Append-only: a row is written per completion by the metering layer
    (:class:`apps.ai.resolver.MeteringProvider`). The org admin's usage report is
    just aggregate queries over this table — ``SUM``/``GROUP BY`` on a relational
    store, which is why this lives in Postgres rather than a separate metrics
    system. ``model``/``provider_type`` are snapshots so history stays correct
    when a config is later edited or deleted.
    """

    tenancy = Tenancy.TENANT_OWNED

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="ai_usage_records",
    )
    # Which saved config served the call. SET_NULL (not CASCADE) so deleting a
    # provider config never erases the spend it incurred; NULL also covers calls
    # served by the operator-wide settings fallback, which has no DB row.
    provider_config = models.ForeignKey(
        AIProviderConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usage_records",
    )
    feature = models.CharField(
        max_length=64,
        help_text="Which AI feature spent the tokens, e.g. 'suggest_threats'.",
    )
    model = models.CharField(max_length=255, help_text="Model snapshot.")
    provider_type = models.CharField(max_length=32, help_text="Provider snapshot.")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_records",
    )
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    # NULL = self-hosted / unpriced (tokens still counted). Six decimal places
    # so sub-cent per-call costs aren't rounded away.
    cost_usd = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # The report always filters by org and a time window, so index that
            # access path directly.
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.feature} · {self.total_tokens} tok · org {self.organization_id}"
