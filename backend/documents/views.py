from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from core.tenancy import get_current_company
from purchases.serializers import PurchaseSerializer
from purchases.services import registrar_compra
from sales.serializers import SaleSerializer
from sales.services import crear_venta

from .image_utils import strip_exif
from .models import Document
from .serializers import DocumentConfirmSerializer, DocumentSerializer, DocumentUploadSerializer
from .tasks import procesar_documento

_TERMINAL_STATUSES = {Document.Status.CONFIRMED, Document.Status.REJECTED}


class DocumentListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        return DocumentUploadSerializer if self.request.method == "POST" else DocumentSerializer

    def get_queryset(self):
        company = get_current_company(self.request)
        return (
            Document.objects.for_company(company)
            .select_related("extraction")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        company = get_current_company(self.request)
        cleaned_image = strip_exif(serializer.validated_data["image"])
        document = serializer.save(
            company=company, uploaded_by=self.request.user, image=cleaned_image
        )
        procesar_documento.delay(document.id)


class DocumentDetailView(generics.RetrieveAPIView):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        company = get_current_company(self.request)
        return Document.objects.for_company(company).select_related("extraction")


class DocumentConfirmView(APIView):
    """Registra de verdad la compra/venta a partir de los datos que el
    usuario revisó y (si hizo falta) corrigió — nunca los que propuso el
    OCR/LLM sin pasar por esta confirmación explícita (ver
    docs/SECURITY.md #7 y docs/ROADMAP.md Fase 9).
    """

    def post(self, request, document_id):
        company = get_current_company(request)
        document = get_object_or_404(Document.objects.for_company(company), pk=document_id)

        if document.status in _TERMINAL_STATUSES:
            return Response(
                {"detail": f"Este documento ya está {document.get_status_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DocumentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        es_venta = data["document_type"] == "sale"
        price_field = "unit_price" if es_venta else "unit_cost"

        items = []
        for raw_item in data["items"]:
            product = get_object_or_404(
                Product.objects.for_company(company), pk=raw_item["product_id"]
            )
            item = {"product": product, "quantity": raw_item["quantity"]}
            if "unit_amount" in raw_item:
                item[price_field] = raw_item["unit_amount"]
            items.append(item)

        try:
            if es_venta:
                resultado = crear_venta(
                    company=company,
                    user=request.user,
                    items=items,
                    customer_name=data["party_name"],
                    origen="document",
                )
                resultado_data = SaleSerializer(resultado).data
            else:
                resultado = registrar_compra(
                    company=company,
                    user=request.user,
                    items=items,
                    supplier_name=data["party_name"],
                    origen="document",
                )
                resultado_data = PurchaseSerializer(resultado).data
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        document.status = Document.Status.CONFIRMED
        document.document_type_guess = data["document_type"]
        document.save(update_fields=["status", "document_type_guess", "updated_at"])

        extraction = getattr(document, "extraction", None)
        if extraction is not None:
            extraction.reviewed_by = request.user
            extraction.reviewed_at = timezone.now()
            extraction.save(update_fields=["reviewed_by", "reviewed_at"])

        return Response(
            {
                "status": "confirmed",
                "document_type": data["document_type"],
                "result": resultado_data,
            }
        )


class DocumentRejectView(APIView):
    def post(self, request, document_id):
        company = get_current_company(request)
        document = get_object_or_404(Document.objects.for_company(company), pk=document_id)

        if document.status in _TERMINAL_STATUSES:
            return Response(
                {"detail": f"Este documento ya está {document.get_status_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document.status = Document.Status.REJECTED
        document.save(update_fields=["status", "updated_at"])
        return Response({"status": document.status})
