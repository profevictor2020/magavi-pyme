from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from core.tenancy import get_current_company
from inventory.services import ajustar_inventario

from .models import Product
from .serializers import AdjustStockSerializer, InventoryMovementSerializer, ProductSerializer
from .services import crear_producto


class ProductViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD de productos con scope de empresa.

    Sin borrado físico (ver docs/DATA_MODEL.md #1): para dar de baja un
    producto se actualiza `is_active` en vez de eliminarlo.
    """

    serializer_class = ProductSerializer

    def get_queryset(self):
        company = get_current_company(self.request)
        queryset = Product.objects.for_company(company)
        if self.request.query_params.get("low_stock") == "true":
            queryset = queryset.filter(current_stock__lte=F("low_stock_threshold"))
        return queryset.order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["company"] = get_current_company(self.request)
        return context

    def perform_create(self, serializer):
        company = get_current_company(self.request)
        product = crear_producto(
            company=company,
            user=self.request.user,
            origen="manual",
            **serializer.validated_data,
        )
        serializer.instance = product

    def perform_update(self, serializer):
        serializer.validated_data.pop("initial_stock", None)
        serializer.save()

    @action(detail=True, methods=["post"], url_path="adjust-stock")
    def adjust_stock(self, request, pk=None):
        company = get_current_company(request)
        product = get_object_or_404(Product.objects.for_company(company), pk=pk)

        serializer = AdjustStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            movement = ajustar_inventario(
                company=company,
                user=request.user,
                product=product,
                cantidad=serializer.validated_data["cantidad"],
                motivo=serializer.validated_data["motivo"],
                origen="manual",
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        return Response(InventoryMovementSerializer(movement).data, status=201)
