from django.contrib import admin

from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "purchased_at", "total", "status", "source"]
    list_filter = ["status", "source"]
    inlines = [PurchaseItemInline]
