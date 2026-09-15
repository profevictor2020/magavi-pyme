from django.contrib import admin

from .models import CashMovement


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = ["company", "type", "amount", "reference_type", "created_at"]
    list_filter = ["type", "reference_type"]
