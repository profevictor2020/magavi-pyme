from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "company", "user", "action", "entity_type", "entity_id", "source"]
    list_filter = ["source", "entity_type"]
    search_fields = ["action", "entity_type", "entity_id"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
