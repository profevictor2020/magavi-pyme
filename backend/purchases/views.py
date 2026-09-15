from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from core.tenancy import get_current_company

from .models import Purchase
from .serializers import PurchaseCreateSerializer, PurchaseSerializer
from .services import registrar_compra


class PurchaseListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        return PurchaseSerializer if self.request.method == "GET" else PurchaseCreateSerializer

    def get_queryset(self):
        company = get_current_company(self.request)
        queryset = Purchase.objects.for_company(company).order_by("-purchased_at")

        date_from = self.request.query_params.get("from")
        date_to = self.request.query_params.get("to")
        if date_from:
            queryset = queryset.filter(purchased_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(purchased_at__date__lte=date_to)

        return queryset

    def create(self, request, *args, **kwargs):
        company = get_current_company(request)
        serializer = PurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items = []
        for raw_item in serializer.validated_data["items"]:
            product = get_object_or_404(
                Product.objects.for_company(company), pk=raw_item["product_id"]
            )
            item = {"product": product, "quantity": raw_item["quantity"]}
            if "unit_cost" in raw_item:
                item["unit_cost"] = raw_item["unit_cost"]
            items.append(item)

        try:
            purchase = registrar_compra(
                company=company,
                user=request.user,
                items=items,
                supplier_name=serializer.validated_data["supplier_name"],
                origen="manual",
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        return Response(PurchaseSerializer(purchase).data, status=status.HTTP_201_CREATED)


class PurchaseSummaryView(APIView):
    """Análogo a SaleSummaryView: compras/egresos de hoy y de la semana."""

    def get(self, request):
        company = get_current_company(request)
        now = timezone.localtime()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timezone.timedelta(days=today_start.weekday())

        base = Purchase.objects.for_company(company).filter(status=Purchase.Status.CONFIRMED)

        def summarize(since):
            aggregate = base.filter(purchased_at__gte=since).aggregate(
                total=Sum("total"), count=Count("id")
            )
            return {
                "total": str(aggregate["total"] or Decimal("0.00")),
                "count": aggregate["count"] or 0,
            }

        return Response({"today": summarize(today_start), "week": summarize(week_start)})
