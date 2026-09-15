from django.db import transaction
from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound

from .models import Company, CompanyUser
from .serializers import CompanySerializer


class CompanyListCreateView(generics.ListCreateAPIView):
    """Lista las empresas del usuario autenticado ("mis empresas") y permite
    crear una empresa nueva, dejando al creador como owner.
    """

    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Company.objects.filter(memberships__user=self.request.user, memberships__is_active=True)
            .distinct()
            .order_by("name")
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            company = serializer.save()
            CompanyUser.objects.create(
                company=company, user=self.request.user, role=CompanyUser.Role.OWNER
            )


class CompanyDetailView(generics.RetrieveAPIView):
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "company_id"

    def get_queryset(self):
        return Company.objects.filter(
            memberships__user=self.request.user, memberships__is_active=True
        ).distinct()

    def get_object(self):
        obj = self.get_queryset().filter(pk=self.kwargs["company_id"]).first()
        if obj is None:
            # 404, no 403: no confirmamos la existencia de una empresa ajena.
            raise NotFound()
        return obj
