"""
Compliance models - frameworks, standards.
"""

from django.db import models

from apps.core.models import TimestampedModel
from apps.core.tenancy import Tenancy
from apps.threats.models import CountermeasureLibrary


class StandardFramework(TimestampedModel):
    """Compliance framework (e.g., PCI-DSS, SOC2, NIST)."""

    # The user-created internal standards are unscoped today: every tenant reads
    # them — precogly/precogly#405.
    tenancy = Tenancy.MIXED

    slug = models.SlugField(max_length=100, unique=True)
    source_pack = models.ForeignKey(
        "packs.LibraryPack",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frameworks",
    )
    threat_model = models.ForeignKey(
        "threat_models.ThreatModel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="internal_frameworks",
        help_text="Populated for user-created internal standards. "
        "NULL for global pack-sourced frameworks.",
    )
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=50)
    issuer = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "version"]

    def __str__(self):
        return f"{self.name} {self.version}"


class StandardRequirement(TimestampedModel):
    """Requirement within a compliance framework."""

    # No nullable key of its own; a requirement belongs to whoever its framework
    # belongs to.
    tenancy = Tenancy.MIXED

    framework = models.ForeignKey(
        StandardFramework,
        on_delete=models.CASCADE,
        related_name="requirements",
    )
    section_code = models.CharField(max_length=50)
    name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField()
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    requirement_type = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=20, blank=True, default="")
    priority = models.CharField(max_length=20, blank=True, default="")
    acceptance_criteria = models.JSONField(default=list, blank=True)
    format_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["framework", "section_code"]

    def __str__(self):
        return f"{self.framework.name} - {self.section_code}"


class CountermeasureLibraryStandard(models.Model):
    """Association between countermeasure and compliance requirement."""

    # Both ends are library rows, so the mapping ships with the packs rather than
    # belonging to whoever happens to use it.
    tenancy = Tenancy.SHARED_REFERENCE

    class Sufficiency(models.TextChoices):
        FULL = "full", "Full"
        PARTIAL = "partial", "Partial"

    countermeasure_library = models.ForeignKey(
        CountermeasureLibrary,
        on_delete=models.CASCADE,
        related_name="standard_mappings",
    )
    # NAVE PATCH (precogly/precogly#338): was on_delete=CASCADE. A
    # typo'd/renamed section_code on a compliance-pack reimport makes
    # apps.packs.services._load_frameworks() treat the OLD StandardRequirement
    # row as removed from the pack -- it prunes any StandardRequirement
    # whose section_code isn't in the freshly-imported YAML
    # (`StandardRequirement.objects.filter(framework=framework).exclude(
    # section_code__in=incoming_section_codes).delete()`), and under
    # CASCADE that silently destroyed every mapping that had pointed at it,
    # with no error or warning -- the same failure family as #318 (pack
    # reimport silently orphaning/destroying downstream data) and #329.
    # SET_NULL matches the design already used one model over for the
    # exact same relationship: `InstanceCountermeasureStandard.requirement`
    # (apps/threats/models.py) has always been `on_delete=SET_NULL,
    # null=True`. Every consumer of this field was audited and updated to
    # skip/null-guard orphaned (requirement=None) rows rather than treat
    # them as real compliance mappings -- see apps/packs/services.py's
    # get_active_overlays_for_pack(), apps/compliance/serializers.py's
    # CountermeasureLibraryStandardSerializer, apps/threat_models/
    # compliance_service.py's drift/sync functions, and apps/diagrams/
    # services.py's instance-mapping propagation.
    #
    # Trade-off, same as #318's own: an orphaned mapping now lingers as a
    # harmless-but-meaningless row (no section_code/name snapshot exists on
    # this model to identify what it used to point to) instead of being
    # silently destroyed. Harmless clutter, not data corruption, and
    # strictly better than losing the sufficiency judgement call
    # (full/partial) a security engineer made, with no record it ever
    # existed.
    requirement = models.ForeignKey(
        StandardRequirement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="countermeasure_mappings",
    )
    sufficiency = models.CharField(
        max_length=10,
        choices=Sufficiency.choices,
        default=Sufficiency.PARTIAL,
    )

    class Meta:
        unique_together = ["countermeasure_library", "requirement"]

    def __str__(self):
        if self.requirement is None:
            return (
                f"{self.countermeasure_library} -> [orphaned requirement] "
                f"({self.sufficiency})"
            )
        return (
            f"{self.countermeasure_library} -> {self.requirement} ({self.sufficiency})"
        )


class StandardRequirementMapping(models.Model):
    """Cross-framework mapping between two compliance requirements.

    Example: NIST CSF PR.AC-4 partially covers OWASP A01:2021.
    Used for gap analysis between compliance standards.
    """

    # A statement about two published standards, true for every installation.
    tenancy = Tenancy.SHARED_REFERENCE

    class Sufficiency(models.TextChoices):
        FULL = "full", "Full"
        PARTIAL = "partial", "Partial"

    # NAVE PATCH (precogly/precogly#338): both FKs below were
    # on_delete=CASCADE -- same bug and same fix as `CountermeasureLibrary
    # Standard.requirement` above (see its comment for the full mechanism
    # and precedent). A typo'd/renamed section_code on either framework
    # side of a cross-framework mapping silently destroyed the mapping
    # when apps.packs.services._load_frameworks() pruned the stale
    # StandardRequirement row it used to point to.
    from_requirement = models.ForeignKey(
        StandardRequirement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_mappings",
    )
    to_requirement = models.ForeignKey(
        StandardRequirement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_mappings",
    )
    sufficiency = models.CharField(
        max_length=10,
        choices=Sufficiency.choices,
        default=Sufficiency.PARTIAL,
    )
    source_pack = models.ForeignKey(
        "packs.LibraryPack",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requirement_mappings",
        help_text="Pack that created this mapping, used for cleanup on pack delete",
    )

    class Meta:
        unique_together = ["from_requirement", "to_requirement"]

    def __str__(self):
        if self.from_requirement is None or self.to_requirement is None:
            return f"[orphaned cross-framework mapping] ({self.sufficiency})"
        return (
            f"{self.from_requirement.framework.slug}:{self.from_requirement.section_code} "
            f"-> {self.to_requirement.framework.slug}:{self.to_requirement.section_code} "
            f"({self.sufficiency})"
        )
