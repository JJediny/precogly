from django.contrib import admin

from .models import LibraryPack, LibraryPackDependency, PendingRequirementOverlay


class LibraryPackDependencyInline(admin.TabularInline):
    model = LibraryPackDependency
    fk_name = "pack"
    extra = 1
    autocomplete_fields = ["depends_on_pack"]


@admin.register(LibraryPack)
class LibraryPackAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "pack_type", "version"]
    list_filter = ["pack_type"]
    search_fields = ["name", "slug", "description", "author"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]
    inlines = [LibraryPackDependencyInline]

    fieldsets = (
        (None, {
            "fields": ("name", "slug", "description", "pack_type")
        }),
        ("Versioning", {
            "fields": ("version",)
        }),
        ("Metadata", {
            "fields": ("author", "icon", "tags")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )


@admin.register(LibraryPackDependency)
class LibraryPackDependencyAdmin(admin.ModelAdmin):
    list_display = ["pack", "depends_on_pack"]
    search_fields = ["pack__name", "pack__slug", "depends_on_pack__name", "depends_on_pack__slug"]
    autocomplete_fields = ["pack", "depends_on_pack"]


@admin.register(PendingRequirementOverlay)
class PendingRequirementOverlayAdmin(admin.ModelAdmin):
    list_display = [
        "pack",
        "source_framework_slug",
        "target_framework_slug",
        "overlay_file_name",
        "mapping_count",
    ]
    list_filter = ["source_framework_slug", "target_framework_slug"]
    search_fields = ["pack__name", "pack__slug"]
