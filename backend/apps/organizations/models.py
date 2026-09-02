"""
Organization models for multi-tenancy and team-based ownership.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampedModel
from apps.core.tenancy import Tenancy


class Organization(TimestampedModel):
    """Organization/tenant model."""

    # The tenant itself: a row belongs to the organization it is.
    tenancy = Tenancy.TENANT_OWNED

    class Plan(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        ENTERPRISE = "enterprise", "Enterprise"

    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, blank=True)
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    business_unit_label = models.CharField(
        max_length=50,
        default="Business Unit",
        help_text="Custom label for the grouping layer (e.g., 'Department', 'Product Area')",
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_primary"],
                condition=models.Q(is_primary=True),
                name="unique_primary_organization",
            )
        ]

    def __str__(self):
        return self.name


class OrganizationMember(TimestampedModel):
    """Organization membership with roles."""

    tenancy = Tenancy.TENANT_OWNED

    class Role(models.TextChoices):
        SECURITY_TEAM = "security_team", "Security Team"
        MEMBER = "member", "Member"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["organization", "user"]
        ordering = ["organization", "user"]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"

    def is_last_security_team_member(self):
        """Return True when demoting/removing this member would leave zero security team members."""
        return (
            self.role == self.Role.SECURITY_TEAM
            and self.organization.members.filter(role=self.Role.SECURITY_TEAM).count()
            <= 1
        )


class BusinessUnit(TimestampedModel):
    """
    Flexible grouping layer between Organization and Team.
    Display label is configurable per organization.
    """

    tenancy = Tenancy.TENANT_OWNED

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="business_units",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, default="")
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        verbose_name_plural = "Business units"
        ordering = ["organization", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=~models.Q(code=""),
                name="unique_business_unit_code_per_org",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.organization})"


class Team(TimestampedModel):
    """
    The functional unit of work. Owns threat models.
    """

    tenancy = Tenancy.TENANT_OWNED

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    business_unit = models.ForeignKey(
        BusinessUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["organization", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=~models.Q(code=""),
                name="unique_team_code_per_org",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.organization})"


class TeamMembership(TimestampedModel):
    """
    Bridge table for User <-> Team relationship.
    Users can belong to multiple teams.
    """

    # The team side carries the organization. A user may be in teams belonging to
    # several organizations, so the membership row belongs to the team's, not the
    # user's.
    tenancy = Tenancy.TENANT_OWNED

    class Role(models.TextChoices):
        LEAD = "lead", "Team Lead"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["team", "user"]
        ordering = ["team", "user"]

    def __str__(self):
        return f"{self.user} @ {self.team} ({self.role})"


class TeamInvitation(TimestampedModel):
    """
    Invitation for users who haven't signed up yet.
    Converted to TeamMembership when user registers.
    """

    tenancy = Tenancy.TENANT_OWNED

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=TeamMembership.Role.choices,
        default=TeamMembership.Role.MEMBER,
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_team_invitations",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["team", "email"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invitation to {self.email} for {self.team}"

    def is_valid(self):
        return self.status == self.Status.PENDING and self.expires_at > timezone.now()

    def accept(self, user):
        """Convert invitation to membership."""
        membership, _created = TeamMembership.objects.get_or_create(
            team=self.team,
            user=user,
            defaults={"role": self.role},
        )
        self.status = self.Status.ACCEPTED
        self.accepted_at = timezone.now()
        self.save(update_fields=["status", "accepted_at"])
        return membership


class MagicLink(TimestampedModel):
    """
    Tokenized URL for read-only threat model sharing.
    """

    # Owned by the shared threat model's organization, and readable without any
    # membership: the token is the credential. Scoping reads to members breaks it.
    tenancy = Tenancy.TENANT_OWNED

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    threat_model = models.ForeignKey(
        "threat_models.ThreatModel",
        on_delete=models.CASCADE,
        related_name="magic_links",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_magic_links",
    )
    expires_at = models.DateTimeField()
    accessed_count = models.PositiveIntegerField(default=0)
    is_revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"MagicLink for {self.threat_model}"

    def is_valid(self):
        return not self.is_revoked and self.expires_at > timezone.now()


class SharedWithMe(TimestampedModel):
    """
    Tracks threat models shared with a user via magic link.
    When a logged-in user accesses a magic link, the threat model is added here.
    """

    # Owned by the shared threat model's organization, and readable by the user
    # outside it that the row grants access to.
    tenancy = Tenancy.TENANT_OWNED

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_threat_models",
    )
    threat_model = models.ForeignKey(
        "threat_models.ThreatModel",
        on_delete=models.CASCADE,
        related_name="shared_with_users",
    )
    magic_link = models.ForeignKey(
        MagicLink,
        on_delete=models.SET_NULL,
        null=True,
        related_name="user_accesses",
    )
    first_accessed_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(auto_now=True)
    access_count = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ["user", "threat_model"]
        ordering = ["-last_accessed_at"]
        verbose_name = "Shared with me"
        verbose_name_plural = "Shared with me"

    def __str__(self):
        return f"{self.threat_model} shared with {self.user}"
