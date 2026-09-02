"""
Threat model domain models.
"""

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.compliance.models import StandardFramework
from apps.core.models import TimestampedModel
from apps.core.tenancy import Tenancy
from apps.organizations.models import Organization
from apps.systems.models import Orgsystem


class ThreatModelQuerySet(models.QuerySet):
    """Queries about who may read which threat models."""

    def visible_to(self, user):
        """Narrow to the threat models `user` is allowed to read.

        Organization membership is the outer bound. Within it, a security team member
        reads every model; everyone else reads the models their teams own, plus the
        ones owned by no team — `owning_team` is nullable for records predating the
        field, and there is no team on them to check against.

        This queryset is the entire read boundary. `CanWrite` and `IsSecurityTeam` both
        return `True` for safe methods (`apps/core/permissions.py`), so nothing else
        narrows a read, and the MCP endpoint has no permission classes running at all —
        it resolves a user from a bearer token and calls this.
        """
        org_ids = user.organization_memberships.values_list(
            "organization_id", flat=True
        )
        visible = self.filter(organization_id__in=org_ids)

        # Security team status is not scoped to an organization: being on one
        # organization's security team grants full visibility in every organization the
        # user belongs to, including ones where they are a plain member. That is
        # precogly/precogly#209, still open. Reproduced here deliberately — this method
        # exists to give the rule one home, not to change it.
        if user.organization_memberships.filter(role="security_team").exists():
            return visible

        team_ids = user.team_memberships.values_list("team_id", flat=True)
        return visible.filter(
            models.Q(owning_team_id__in=team_ids) | models.Q(owning_team__isnull=True)
        )


class ThreatModel(TimestampedModel):
    """Threat model."""

    # One of the seven models carrying `organization` directly, and the anchor most of
    # the rest of the schema reaches an organization through.
    tenancy = Tenancy.TENANT_OWNED

    objects = ThreatModelQuerySet.as_manager()

    class Criticality(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="threat_models",
    )
    owning_team = models.ForeignKey(
        "organizations.Team",
        on_delete=models.PROTECT,
        related_name="threat_models",
        null=True,
        blank=True,
        help_text="Team that owns this threat model (nullable during migration)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_threat_models",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    criticality = models.CharField(
        max_length=20,
        choices=Criticality.choices,
        default=Criticality.MEDIUM,
    )
    risk_scoring_method = models.CharField(
        max_length=20,
        choices=[
            ("tm_library", "Likelihood x Impact (5x5 Matrix)"),
            ("fair", "FAIR"),
            ("owasp_rr", "OWASP Risk Rating"),
            ("mozilla_rra", "Mozilla Rapid Risk Assessment"),
            ("custom", "Manual Score"),
        ],
        default="tm_library",
        help_text="Scoring methodology used for all risks in this threat model",
    )
    format_metadata = models.JSONField(default=dict, blank=True)
    # Store system context, progress, etc.
    workspace_data = models.JSONField(default=dict, blank=True)
    assumptions = models.JSONField(default=list, blank=True)
    scope_locked = models.BooleanField(default=False)
    scope_locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ThreatModelOrgsystem(models.Model):
    """Association between threat model and orgsystem."""

    tenancy = Tenancy.TENANT_OWNED

    threat_model = models.ForeignKey(
        ThreatModel,
        on_delete=models.CASCADE,
        related_name="orgsystem_associations",
    )
    orgsystem = models.ForeignKey(
        Orgsystem,
        on_delete=models.CASCADE,
        related_name="threat_model_associations",
    )

    class Meta:
        unique_together = ["threat_model", "orgsystem"]

    def __str__(self):
        return f"{self.threat_model} - {self.orgsystem}"


class ThreatModelLibraryPack(models.Model):
    """Association between threat model and library pack."""

    # The link is tenant-owned even though the pack it names is not: which packs a
    # threat model has connected is that organization's business.
    tenancy = Tenancy.TENANT_OWNED

    threat_model = models.ForeignKey(
        ThreatModel,
        on_delete=models.CASCADE,
        related_name="pack_associations",
    )
    library_pack = models.ForeignKey(
        "packs.LibraryPack",
        on_delete=models.CASCADE,
        related_name="threat_model_associations",
    )

    class Meta:
        unique_together = ["threat_model", "library_pack"]

    def __str__(self):
        return f"{self.threat_model} - {self.library_pack}"


class ThreatModelRelationship(TimestampedModel):
    """Relationship between threat models."""

    tenancy = Tenancy.TENANT_OWNED

    class RelationType(models.TextChoices):
        DEPENDS_ON = "depends_on", "Depends On"
        SUBSYSTEM_OF = "subsystem_of", "Subsystem Of"
        RELATED_TO = "related_to", "Related To"
        SUPERSEDED_BY = "superseded_by", "Superseded By"

    source_threat_model = models.ForeignKey(
        ThreatModel,
        on_delete=models.CASCADE,
        related_name="outgoing_relationships",
    )
    target_threat_model = models.ForeignKey(
        ThreatModel,
        on_delete=models.CASCADE,
        related_name="incoming_relationships",
    )
    relation_type = models.CharField(max_length=20, choices=RelationType.choices)

    class Meta:
        unique_together = [
            "source_threat_model",
            "target_threat_model",
            "relation_type",
        ]

    def __str__(self):
        return f"{self.source_threat_model} {self.relation_type} {self.target_threat_model}"


class ThreatModelFramework(models.Model):
    """Association between threat model and compliance framework."""

    tenancy = Tenancy.TENANT_OWNED

    threat_model = models.ForeignKey(
        ThreatModel,
        on_delete=models.CASCADE,
        related_name="framework_associations",
    )
    framework = models.ForeignKey(
        StandardFramework,
        on_delete=models.CASCADE,
        related_name="threat_model_associations",
    )

    class Meta:
        unique_together = ["threat_model", "framework"]

    def __str__(self):
        return f"{self.threat_model} - {self.framework}"


class ThreatModelReferenceImage(TimestampedModel):
    """Reference image for threat model (whiteboard photos, architecture diagrams, etc.)."""

    tenancy = Tenancy.TENANT_OWNED

    threat_model = models.ForeignKey(
        ThreatModel,
        on_delete=models.CASCADE,
        related_name="reference_images",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_reference_images",
    )
    image = models.ImageField(
        upload_to="reference_images/%Y/%m/",
        help_text="Reference image file (JPEG, PNG, WebP)",
    )
    filename = models.CharField(
        max_length=255,
        help_text="Original filename for display",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of what this image shows",
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Order in gallery (lower = first)",
    )

    class Meta:
        ordering = ["display_order", "-created_at"]

    def __str__(self):
        return f"{self.filename} - {self.threat_model.name}"


class OutOfScopeItem(TimestampedModel):
    """Out-of-scope item for a threat model."""

    tenancy = Tenancy.TENANT_OWNED

    threat_model = models.ForeignKey(
        ThreatModel,
        on_delete=models.CASCADE,
        related_name="out_of_scope_items",
    )
    name = models.CharField(max_length=255)
    reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UseCase(TimestampedModel):
    """Use case associated with a threat model (CycloneDX 2.0 TM-BOM)."""

    tenancy = Tenancy.TENANT_OWNED

    threat_model = models.ForeignKey(
        ThreatModel,
        on_delete=models.CASCADE,
        related_name="use_cases",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    flow_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured use case data: preconditions, postconditions, "
        "success_criteria, main_flow, alternative_flows, exceptions",
    )
    format_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


@receiver(post_delete, sender=ThreatModelReferenceImage)
def delete_reference_image_file(sender, instance, **kwargs):
    """
    Delete the image file from storage when the model instance is deleted.
    """
    if instance.image:
        # Delete the file from storage
        instance.image.delete(save=False)
