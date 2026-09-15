from django.contrib import admin

from .models import InventoryMovement


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ["company", "product", "type", "quantity", "balance_after", "created_at"]
    list_filter = ["type", "reference_type"]
