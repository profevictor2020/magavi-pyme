from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.factories import UserFactory
from audit.models import AuditLog
from companies.factories import CompanyFactory
from inventory.models import InventoryMovement

from .factories import ProductFactory
from .models import Product
from .services import crear_producto


class CrearProductoTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()

    def test_creates_product_with_given_fields(self):
        product = crear_producto(
            company=self.company,
            user=self.user,
            name="Café molido",
            unit=Product.Unit.KG,
            default_price=Decimal("3000"),
            default_cost=Decimal("1800"),
        )

        self.assertEqual(product.name, "Café molido")
        self.assertEqual(product.unit, Product.Unit.KG)
        self.assertEqual(product.default_price, Decimal("3000"))
        self.assertEqual(product.current_stock, Decimal("0.000"))

    def test_zero_initial_stock_creates_no_movement(self):
        product = crear_producto(company=self.company, user=self.user, name="Sin stock")

        self.assertEqual(
            InventoryMovement.objects.for_company(self.company)
            .filter(product=product)
            .count(),
            0,
        )

    def test_initial_stock_seeds_via_inventory_movement(self):
        product = crear_producto(
            company=self.company, user=self.user, name="Azúcar", initial_stock=Decimal("20")
        )

        self.assertEqual(product.current_stock, Decimal("20.000"))
        movement = InventoryMovement.objects.for_company(self.company).get(product=product)
        # origen="manual" (default): ajustar_inventario siempre clasifica
        # esto como "adjustment", no "in" (ver inventory/services.py).
        self.assertEqual(movement.type, InventoryMovement.MovementType.ADJUSTMENT)
        self.assertEqual(movement.quantity, Decimal("20.000"))

    def test_rejects_duplicate_sku_in_same_company(self):
        ProductFactory(company=self.company, sku="ABC-1")

        with self.assertRaises(ValidationError):
            crear_producto(company=self.company, user=self.user, name="Otro", sku="ABC-1")

    def test_same_sku_allowed_in_different_company(self):
        other_company = CompanyFactory()
        ProductFactory(company=other_company, sku="ABC-1")

        product = crear_producto(company=self.company, user=self.user, name="Otro", sku="ABC-1")

        self.assertEqual(product.sku, "ABC-1")

    def test_writes_audit_log(self):
        product = crear_producto(company=self.company, user=self.user, name="Té")

        entry = AuditLog.objects.get(entity_type="Product", entity_id=str(product.id))
        self.assertEqual(entry.action, "product.create")
        self.assertEqual(entry.source, AuditLog.Source.UI)

    def test_assistant_origin_maps_to_assistant_audit_source(self):
        product = crear_producto(
            company=self.company, user=self.user, name="Té verde", origen="assistant"
        )

        entry = AuditLog.objects.get(entity_type="Product", entity_id=str(product.id))
        self.assertEqual(entry.source, AuditLog.Source.ASSISTANT)
