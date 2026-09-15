from django.conf import settings
from django.db import models

from core.managers import CompanyScopedManager


class Company(models.Model):
    name = models.CharField(max_length=255)
    rut = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CompanyUser(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "user"], name="unique_company_user"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.role})"


class Module(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.code


class CompanyModule(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="modules")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="companies")
    enabled = models.BooleanField(default=True)
    enabled_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "module"], name="unique_company_module"),
        ]

    def __str__(self):
        return f"{self.module} @ {self.company}"
