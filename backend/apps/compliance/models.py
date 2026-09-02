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
    requirement = models.ForeignKey(
        StandardRequirement,
        on_delete=models.CASCADE,
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

    from_requirement = models.ForeignKey(
        StandardRequirement,
        on_delete=models.CASCADE,
        related_name="outgoing_mappings",
    )
    to_requirement = models.ForeignKey(
        StandardRequirement,
        on_delete=models.CASCADE,
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
        return (
            f"{self.from_requirement.framework.slug}:{self.from_requirement.section_code} "
            f"-> {self.to_requirement.framework.slug}:{self.to_requirement.section_code} "
            f"({self.sufficiency})"
        )
