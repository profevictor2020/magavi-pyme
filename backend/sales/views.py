from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from core.tenancy import get_current_company

from .models import Sale
from .serializers import SaleCreateSerializer, SaleSerializer
from .services import consultar_ventas, crear_venta


class SaleListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        return SaleSerializer if self.request.method == "GET" else SaleCreateSerializer

    def get_queryset(self):
        company = get_current_company(self.request)
        queryset = Sale.objects.for_company(company).order_by("-sold_at")

        date_from = self.request.query_params.get("from")
        date_to = self.request.query_params.get("to")
        if date_from:
            queryset = queryset.filter(sold_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(sold_at__date__lte=date_to)

        return queryset

    def create(self, request, *args, **kwargs):
        company = get_current_company(request)
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items = []
        for raw_item in serializer.validated_data["items"]:
            product = get_object_or_404(
                Product.objects.for_company(company), pk=raw_item["product_id"]
            )
            item = {"product": product, "quantity": raw_item["quantity"]}
            if "unit_price" in raw_item:
                item["unit_price"] = raw_item["unit_price"]
            items.append(item)

        try:
            sale = crear_venta(
                company=company,
                user=request.user,
                items=items,
                customer_name=serializer.validated_data["customer_name"],
                origen="manual",
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)


class SaleSummaryView(APIView):
    """Soporte directo al guion de demo: "¿cuánto vendí hoy?" / "esta
    semana". Se reutilizará como fuente de datos del asistente (Fase 8).
    """

    def get(self, request):
        company = get_current_company(request)
        return Response(consultar_ventas(company=company))
