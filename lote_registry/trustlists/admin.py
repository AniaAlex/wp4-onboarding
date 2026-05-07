from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Entity, LotlPointer, Operator, PublishRun, Scheme


@admin.register(Operator)
class OperatorAdmin(UserAdmin):
    list_display = ("email", "display_name", "territory", "role", "is_staff", "is_active")
    list_filter = ("role", "territory", "is_staff", "is_superuser")
    search_fields = ("email", "display_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "territory", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Audit", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "display_name", "territory", "role"),
        }),
    )


class EntityInline(admin.StackedInline):
    model = Entity
    extra = 0
    fields = ("entity_id", "names", "entity_type", "status", "address", "information_uri", "services", "cert_pem", "jwk", "did_uri")


class LotlPointerInline(admin.TabularInline):
    model = LotlPointer
    extra = 0
    fields = ("scheme_territory", "scheme_type", "location", "mime_type")


@admin.register(Scheme)
class SchemeAdmin(admin.ModelAdmin):
    list_display = ("list_type", "territory", "sequence_number", "owner", "entity_count", "public_url")
    list_filter = ("list_type", "territory")
    search_fields = ("operator_names", "scheme_name")
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("list_type", "territory", "sequence_number", "scheme_type", "owner")}),
        ("Names", {"fields": ("operator_names", "scheme_name")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    def get_inlines(self, request, obj=None):
        if obj and obj.list_type == "lotl":
            return [LotlPointerInline]
        return [EntityInline]

    @admin.display(description="entities", ordering="entities__count")
    def entity_count(self, obj):
        return obj.entities.count() if obj.list_type != "lotl" else obj.lotl_pointers.count()


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("entity_id", "scheme", "entity_type", "status")
    list_filter = ("scheme__list_type", "entity_type")
    search_fields = ("entity_id", "names")
    autocomplete_fields = ("scheme",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(LotlPointer)
class LotlPointerAdmin(admin.ModelAdmin):
    list_display = ("scheme_territory", "scheme_type", "location", "mime_type")
    list_filter = ("scheme_territory", "mime_type")
    autocomplete_fields = ("scheme",)


@admin.register(PublishRun)
class PublishRunAdmin(admin.ModelAdmin):
    list_display = ("scheme", "status", "triggered_by", "created_at", "fingerprint")
    list_filter = ("status", "scheme__list_type")
    autocomplete_fields = ("scheme", "triggered_by")
    readonly_fields = ("created_at", "updated_at", "fingerprint", "request_payload", "response")
    ordering = ("-created_at",)
