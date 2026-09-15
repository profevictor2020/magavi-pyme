from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "sold_at", "total", "status", "source"]
    list_filter = ["status", "source"]
    inlines = [SaleItemInline]
