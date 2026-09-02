"""
Systems models - Orgsystems, components, data flows.
"""

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimestampedModel
from apps.core.tenancy import Tenancy
from apps.organizations.models import Organization


class Orgsystem(TimestampedModel):
    """Organizational system being modeled."""

    tenancy = Tenancy.TENANT_OWNED

    class Criticality(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class LifecycleState(models.TextChoices):
        DEVELOPMENT = "development", "Development"
        PRODUCTION = "production", "Production"
        DECOMMISSIONED = "decommissioned", "Decommissioned"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="orgsystems",
    )
    name = models.CharField(max_length=255)
    owner = models.CharField(max_length=255, blank=True)
    criticality = models.CharField(
        max_length=20,
        choices=Criticality.choices,
        default=Criticality.MEDIUM,
    )
    lifecycle_state = models.CharField(
        max_length=20,
        choices=LifecycleState.choices,
        default=LifecycleState.DEVELOPMENT,
    )
    description = models.TextField(blank=True, default="")
    format_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class IntegrationSource(TimestampedModel):
    """External integration source for component discovery."""

    tenancy = Tenancy.TENANT_OWNED

    class SourceType(models.TextChoices):
        GITHUB = "github", "GitHub"
        CSPM = "cspm", "CSPM"
        TERRAFORM = "terraform", "Terraform"
        SBOM = "sbom", "SBOM"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ERROR = "error", "Error"

    orgsystem = models.ForeignKey(
        Orgsystem,
        on_delete=models.CASCADE,
        related_name="integration_sources",
    )
    name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    connection_details = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.source_type})"


class TrustZone(TimestampedModel):
    """Trust zone (named security region)."""

    tenancy = Tenancy.TENANT_OWNED

    # A zone used to be reached only in reverse, through `components`, and both hops
    # to an organization were nullable. #404 read across tenants that way and #406
    # wrote through it. This column is the boundary now; nothing should re-derive it.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="trust_zones",
    )
    name = models.CharField(max_length=255)
    trust_level = models.IntegerField(default=50, help_text="0-100 scale")
    description = models.TextField(blank=True)
    format_metadata = models.JSONField(default=dict, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        verbose_name_plural = "Trust zones"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TrustBoundary(TimestampedModel):
    """Security boundary between two trust zones."""

    tenancy = Tenancy.TENANT_OWNED

    # Carries its own owner rather than reading it off `zone_a`: the two zones are
    # separate rows and nothing but this column stops a boundary being drawn between
    # organizations. Lifecycle still comes from the zones, which cascade.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="trust_boundaries",
    )
    zone_a = models.ForeignKey(
        TrustZone,
        on_delete=models.CASCADE,
        related_name="boundaries_as_source",
    )
    zone_b = models.ForeignKey(
        TrustZone,
        on_delete=models.CASCADE,
        related_name="boundaries_as_target",
    )
    label = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    edge_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="DFD edge ID this boundary was created from",
    )
    format_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Auth methods, access control, token TTL, etc.",
    )

    # Crossing requirements (CycloneDX 2.0 TM-BOM)
    authentication = models.BooleanField(default=False)
    authorization = models.BooleanField(default=False)
    data_validation = models.BooleanField(default=False)
    logging = models.BooleanField(default=False)
    monitoring = models.BooleanField(default=False)
    rate_limiting = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Trust boundaries"
        ordering = ["zone_a", "zone_b"]
        unique_together = ["zone_a", "zone_b"]

    def __str__(self):
        return self.label or f"{self.zone_a} <-> {self.zone_b}"


class ComponentLibrary(TimestampedModel):
    """Reusable component templates."""

    # `customization_status` records one tenant's edits to a shipped row, and every
    # tenant then reads the edited row.
    tenancy = Tenancy.MIXED

    class Category(models.TextChoices):
        PROCESS = "process", "Process"
        DATASTORE = "datastore", "Data Store"
        EXTERNAL_HUMAN_ACTOR = "external_human_actor", "External Human Actor"
        EXTERNAL_SYSTEM_ACTOR = "external_system_actor", "External System Actor"

    class CustomizationStatus(models.TextChoices):
        ORIGINAL = "original", "Original (from pack)"
        CUSTOMIZED = "customized", "Customized (user edited)"
        DETACHED = "detached", "Detached (unlinked from pack)"

    source_pack = models.ForeignKey(
        "packs.LibraryPack",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="components",
        help_text="Pack this item came from (null = custom or legacy)",
    )
    slug = models.SlugField(
        max_length=100,
        blank=True,
        help_text="Unique identifier within pack, e.g., 'aws-s3'",
    )
    # `null=True` is required by `unique_component_qualified_slug` below. Postgres
    # treats NULLs as distinct under a unique index, so any number of rows may carry no
    # qualified slug; `blank=True` with `""` would make the second such row collide
    # with the first. DJ001 cannot see the constraint.
    qualified_slug = models.CharField(  # noqa: DJ001
        max_length=200,
        null=True,
        blank=True,
        db_index=True,
        help_text="Namespace-safe identifier, e.g., 'aws-technologies/s3'",
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=Category.choices)
    component_type = models.CharField(max_length=100)
    provider = models.CharField(max_length=100, blank=True)

    # Customization tracking (for update vs fork handling)
    customization_status = models.CharField(
        max_length=20,
        choices=CustomizationStatus.choices,
        default=CustomizationStatus.ORIGINAL,
    )
    base_item_qualified_slug = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        help_text="Original item this was forked/customized from",
    )

    # Backward compatibility for renamed slugs
    aliases = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Previous slugs for backward compatibility",
    )

    # Parent component hierarchy (process-only, max 3 levels)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent component in hierarchy (process category only)",
    )

    MAX_HIERARCHY_DEPTH = 3

    class Meta:
        verbose_name_plural = "Component libraries"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["qualified_slug"],
                name="unique_component_qualified_slug",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"

    def clean(self):
        super().clean()
        if self.parent:
            if self.category != self.Category.PROCESS:
                raise ValidationError(
                    {"parent": "Only process-category components can have a parent."}
                )
            if self.parent.category != self.Category.PROCESS:
                raise ValidationError(
                    {"parent": "Parent must be a process-category component."}
                )
            if self.parent_id == self.pk:
                raise ValidationError(
                    {"parent": "A component cannot be its own parent."}
                )
            self._validate_no_circular_reference()
            self._validate_max_depth()

    def _validate_no_circular_reference(self):
        """Walk up the parent chain to detect cycles."""
        visited = {self.pk}
        current = self.parent
        while current is not None:
            if current.pk in visited:
                raise ValidationError({"parent": "Circular parent reference detected."})
            visited.add(current.pk)
            current = current.parent

    def _validate_max_depth(self):
        """Ensure total hierarchy depth does not exceed MAX_HIERARCHY_DEPTH."""
        # Count levels above (ancestors)
        ancestor_depth = 0
        current = self.parent
        while current is not None:
            ancestor_depth += 1
            current = current.parent

        # Count levels below (descendants)
        descendant_depth = self._get_descendant_depth()

        # Total depth = ancestors + self + descendants
        total_depth = ancestor_depth + 1 + descendant_depth
        if total_depth > self.MAX_HIERARCHY_DEPTH:
            raise ValidationError(
                {
                    "parent": f"Hierarchy depth would exceed maximum of "
                    f"{self.MAX_HIERARCHY_DEPTH} levels."
                }
            )

    def _get_descendant_depth(self):
        """Return the deepest level of descendants below this node."""
        max_depth = 0
        for child in self.children.all():
            child_depth = 1 + child._get_descendant_depth()
            max_depth = max(max_depth, child_depth)
        return max_depth

    def save(self, *args, **kwargs):
        # Auto-generate qualified_slug if not set
        if not self.qualified_slug and self.slug:
            if self.source_pack:
                self.qualified_slug = f"{self.source_pack.slug}/{self.slug}"
            else:
                self.qualified_slug = f"custom/{self.slug}"
        super().save(*args, **kwargs)


class OrgsystemComponent(TimestampedModel):
    """Component instance, optionally linked to an orgsystem."""

    # "Optionally linked" is the nullable `orgsystem` that made #227 possible: with it
    # null the organization is reached through `threat_model` instead, and the queryset
    # has to cover both.
    tenancy = Tenancy.TENANT_OWNED

    orgsystem = models.ForeignKey(
        Orgsystem,
        on_delete=models.CASCADE,
        related_name="components",
        null=True,
        blank=True,
        help_text="Optional link to a system. Null means component exists without system assignment.",
    )
    component_library = models.ForeignKey(
        ComponentLibrary,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instances",
        help_text="Null means orphaned/custom component (library item was removed)",
    )
    name = models.CharField(max_length=255)
    trust_zone = models.ForeignKey(
        TrustZone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="components",
    )
    source_integration = models.ForeignKey(
        IntegrationSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovered_components",
    )
    threat_model = models.ForeignKey(
        "threat_models.ThreatModel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="analysis_components",
        help_text="For analysis-only components not linked to a DFD. Null means linked via DFD sync.",
    )

    description = models.TextField(blank=True, default="")
    actor_type = models.CharField(max_length=20, blank=True, default="")
    data_store_type = models.CharField(max_length=20, blank=True, default="")
    data_sensitivity_level = models.CharField(max_length=20, blank=True, default="")
    parent_component = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    format_metadata = models.JSONField(default=dict, blank=True)

    # Metadata copied from library on creation (for self-sufficiency if orphaned)
    # TODO: drop `null=True` and migrate existing NULLs to "". `component_type` and
    # `provider` below are copied from the library the same way and both spell "not
    # set" as `blank=True` alone, so this field is the odd one of the three.
    #
    # The migration changes .tm export output. `adapters/tm_library.py` exports a
    # component as an actor when `comp.category is None` and its format_metadata
    # carries an `original_type`; migrating the NULLs stops that branch firing, and
    # relaxing it to `not comp.category` newly catches rows already holding "".
    # No test covers either direction.
    category = models.CharField(  # noqa: DJ001
        max_length=30,
        blank=True,
        null=True,
        help_text="Copied from ComponentLibrary.category on creation",
    )
    component_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Copied from ComponentLibrary.component_type on creation",
    )
    provider = models.CharField(
        max_length=100,
        blank=True,
        help_text="Copied from ComponentLibrary.provider on creation",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DataAsset(TimestampedModel):
    """Data asset with classification."""

    tenancy = Tenancy.TENANT_OWNED

    class Sensitivity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    threat_model = models.ForeignKey(
        "threat_models.ThreatModel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="data_assets",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    classification = models.CharField(max_length=100)
    confidentiality = models.CharField(
        max_length=10,
        choices=Sensitivity.choices,
        default=Sensitivity.MEDIUM,
    )
    integrity = models.CharField(
        max_length=10,
        choices=Sensitivity.choices,
        default=Sensitivity.MEDIUM,
    )
    availability = models.CharField(
        max_length=10,
        choices=Sensitivity.choices,
        default=Sensitivity.MEDIUM,
    )
    compliance_tags = models.JSONField(default=list, blank=True)
    data_sensitivity = models.JSONField(default=list, blank=True)
    format_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.data_sensitivity:
            seen = set()
            normalized = []
            for tag in self.data_sensitivity:
                t = str(tag).strip().lower()
                if t and t not in seen:
                    seen.add(t)
                    normalized.append(t)
            self.data_sensitivity = normalized
        super().save(*args, **kwargs)


class ComponentDataAsset(TimestampedModel):
    """Association between component and data asset."""

    tenancy = Tenancy.TENANT_OWNED

    class DataState(models.TextChoices):
        AT_REST = "at_rest", "At Rest"
        PROCESSED = "processed", "Processed"

    component = models.ForeignKey(
        OrgsystemComponent,
        on_delete=models.CASCADE,
        related_name="data_assets",
    )
    data_asset = models.ForeignKey(
        DataAsset,
        on_delete=models.CASCADE,
        related_name="component_associations",
    )
    data_state = models.CharField(
        max_length=20,
        choices=DataState.choices,
        default=DataState.PROCESSED,
    )
    volume = models.CharField(max_length=100, blank=True)
    encrypted = models.BooleanField(default=False)

    class Meta:
        unique_together = ["component", "data_asset"]

    def __str__(self):
        return f"{self.component} - {self.data_asset}"


class DataFlow(TimestampedModel):
    """Data flow between components."""

    tenancy = Tenancy.TENANT_OWNED

    source_component = models.ForeignKey(
        OrgsystemComponent,
        on_delete=models.CASCADE,
        related_name="outgoing_flows",
    )
    dest_component = models.ForeignKey(
        OrgsystemComponent,
        on_delete=models.CASCADE,
        related_name="incoming_flows",
    )
    label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display label for the data flow",
    )
    edge_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="DFD edge ID this flow was created from",
    )
    description = models.TextField(blank=True, default="")
    protocol = models.CharField(max_length=50, blank=True)
    port = models.IntegerField(null=True, blank=True)
    encrypted = models.BooleanField(default=False)
    authenticated = models.BooleanField(default=False)
    crosses_trust_zone = models.BooleanField(default=False)
    has_sensitive_data = models.BooleanField(default=False)
    data_classification = models.JSONField(default=list, blank=True)
    format_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["source_component", "dest_component"]

    def __str__(self):
        if self.label:
            return self.label
        return f"{self.source_component} -> {self.dest_component}"

    def save(self, *args, **kwargs):
        if self.data_classification:
            seen = set()
            normalized = []
            for tag in self.data_classification:
                t = str(tag).strip().lower()
                if t and t not in seen:
                    seen.add(t)
                    normalized.append(t)
            self.data_classification = normalized
        super().save(*args, **kwargs)


class DataFlowAsset(TimestampedModel):
    """Data assets transported in a data flow."""

    tenancy = Tenancy.TENANT_OWNED

    class ProtectionMethod(models.TextChoices):
        ENCRYPTED = "encrypted", "Encrypted"
        MASKED = "masked", "Masked"
        TOKENIZED = "tokenized", "Tokenized"
        HASHED = "hashed", "Hashed"
        NONE = "none", "None"

    data_flow = models.ForeignKey(
        DataFlow,
        on_delete=models.CASCADE,
        related_name="assets",
    )
    data_asset = models.ForeignKey(
        DataAsset,
        on_delete=models.CASCADE,
        related_name="flow_associations",
    )
    protection_method = models.CharField(
        max_length=20,
        choices=ProtectionMethod.choices,
        default=ProtectionMethod.NONE,
    )
    encryption_type = models.CharField(max_length=50, blank=True)
    format = models.CharField(max_length=50, blank=True)
    sensitivity_override = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ["data_flow", "data_asset"]

    def __str__(self):
        return f"{self.data_flow} - {self.data_asset}"
