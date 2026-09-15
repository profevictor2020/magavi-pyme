from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "sku", "current_stock", "is_active"]
    list_filter = ["is_active", "unit"]
    search_fields = ["name", "sku"]
