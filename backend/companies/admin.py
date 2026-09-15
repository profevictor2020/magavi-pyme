from django.contrib import admin

from .models import Company, CompanyModule, CompanyUser, Module


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "rut", "is_active", "created_at"]
    search_fields = ["name", "rut"]


@admin.register(CompanyUser)
class CompanyUserAdmin(admin.ModelAdmin):
    list_display = ["company", "user", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active"]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]


@admin.register(CompanyModule)
class CompanyModuleAdmin(admin.ModelAdmin):
    list_display = ["company", "module", "enabled", "enabled_at"]
