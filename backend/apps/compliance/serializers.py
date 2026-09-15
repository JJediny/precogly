"""
Serializers for compliance app.
"""

from rest_framework import serializers

from .models import (
    CountermeasureLibraryStandard,
    StandardFramework,
    StandardRequirement,
)


class StandardFrameworkSerializer(serializers.ModelSerializer):
    """Serializer for StandardFramework model."""

    class Meta:
        model = StandardFramework
        fields = [
            "id",
            "name",
            "version",
            "issuer",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StandardFrameworkListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for framework listing (matches frontend type)."""

    class Meta:
        model = StandardFramework
        fields = ["id", "name", "version", "issuer", "description", "source_pack"]


class StandardRequirementSerializer(serializers.ModelSerializer):
    """Serializer for StandardRequirement model."""

    framework_name = serializers.CharField(source="framework.name", read_only=True)
    source_pack = serializers.IntegerField(
        source="framework.source_pack_id", read_only=True
    )

    class Meta:
        model = StandardRequirement
        fields = [
            "id",
            "framework",
            "framework_name",
            "source_pack",
            "section_code",
            "description",
            "parent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "framework_name",
            "source_pack",
        ]


class CountermeasureLibraryStandardSerializer(serializers.ModelSerializer):
    """Serializer for countermeasure-standard mappings."""

    # NAVE PATCH (precogly/precogly#338): `requirement` is now nullable
    # (apps/compliance/models.py -- CASCADE -> SET_NULL, see that model's
    # comment). Plain `CharField(source="requirement.section_code")` would
    # raise AttributeError on `None.section_code` for an orphaned mapping
    # row -- DRF's attribute-traversal helper only swallows
    # ObjectDoesNotExist, not a plain AttributeError from a None
    # intermediate. SerializerMethodField with an explicit None-check
    # avoids that.
    requirement_code = serializers.SerializerMethodField()
    framework_name = serializers.SerializerMethodField()

    def get_requirement_code(self, obj):
        return obj.requirement.section_code if obj.requirement else None

    def get_framework_name(self, obj):
        return obj.requirement.framework.name if obj.requirement else None

    class Meta:
        model = CountermeasureLibraryStandard
        fields = [
            "id",
            "countermeasure_library",
            "requirement",
            "requirement_code",
            "framework_name",
            "sufficiency",
        ]
        read_only_fields = ["requirement_code", "framework_name"]
