from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.factories import UserFactory
from audit.models import AuditLog
from companies.factories import CompanyFactory
from inventory.models import InventoryMovement

from .factories import ProductFactory
from .models import Product
from .services import actualizar_producto, crear_producto


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

    def test_rejects_duplicate_name_in_same_company(self):
        # Bug real (ver docs/DECISIONS.md ADR-027): "el stock de cuaderno
        # es de 200" / "y este cuaderno lo vamos a vender a 1750" en
        # mensajes de seguimiento terminaron creando dos "cuaderno" MÁS
        # (tres en total) en vez de actualizar el que ya existía — el
        # Tool Layer rechaza el duplicado como última línea de defensa,
        # independiente de qué intent haya elegido el LLM.
        crear_producto(company=self.company, user=self.user, name="Cuaderno")

        with self.assertRaises(ValidationError):
            crear_producto(company=self.company, user=self.user, name="Cuaderno")

    def test_rechaza_nombre_duplicado_sin_importar_mayusculas_o_espacios(self):
        crear_producto(company=self.company, user=self.user, name="Cuaderno")

        with self.assertRaises(ValidationError):
            crear_producto(company=self.company, user=self.user, name="  cuaderno  ")

    def test_permite_reusar_nombre_de_un_producto_inactivo(self):
        producto = crear_producto(company=self.company, user=self.user, name="Cuaderno")
        producto.is_active = False
        producto.save(update_fields=["is_active"])

        nuevo = crear_producto(company=self.company, user=self.user, name="Cuaderno")

        self.assertEqual(nuevo.name, "Cuaderno")

    def test_mismo_nombre_permitido_en_otra_empresa(self):
        other_company = CompanyFactory()
        other_user = UserFactory()
        crear_producto(company=other_company, user=other_user, name="Cuaderno")

        producto = crear_producto(company=self.company, user=self.user, name="Cuaderno")

        self.assertEqual(producto.name, "Cuaderno")

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


class ActualizarProductoTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(
            company=self.company,
            name="Goma",
            default_price=Decimal("500.00"),
            default_cost=Decimal("200.00"),
        )

    def test_updates_only_the_given_field(self):
        product = actualizar_producto(
            company=self.company, user=self.user, product=self.product, default_price=Decimal("890")
        )

        self.assertEqual(product.default_price, Decimal("890.00"))
        # Los campos no mencionados quedan intactos.
        self.assertEqual(product.default_cost, Decimal("200.00"))
        self.assertEqual(product.name, "Goma")

    def test_updates_multiple_fields_at_once(self):
        product = actualizar_producto(
            company=self.company,
            user=self.user,
            product=self.product,
            name="Goma de borrar",
            default_price=Decimal("990"),
            low_stock_threshold=Decimal("5"),
        )

        self.assertEqual(product.name, "Goma de borrar")
        self.assertEqual(product.default_price, Decimal("990.00"))
        self.assertEqual(product.low_stock_threshold, Decimal("5.000"))

    def test_never_touches_current_stock(self):
        self.product.current_stock = Decimal("42")
        self.product.save(update_fields=["current_stock"])

        product = actualizar_producto(
            company=self.company, user=self.user, product=self.product, default_price=Decimal("890")
        )

        self.assertEqual(product.current_stock, Decimal("42.000"))

    def test_rejects_call_with_no_fields_to_update(self):
        with self.assertRaises(ValidationError):
            actualizar_producto(company=self.company, user=self.user, product=self.product)

    def test_writes_audit_log_with_before_and_after(self):
        actualizar_producto(
            company=self.company, user=self.user, product=self.product, default_price=Decimal("890")
        )

        entry = AuditLog.objects.get(entity_type="Product", entity_id=str(self.product.id))
        self.assertEqual(entry.action, "product.update")
        self.assertEqual(entry.before["default_price"], "500.00")
        self.assertEqual(entry.after["default_price"], "890")

    def test_assistant_origin_maps_to_assistant_audit_source(self):
        actualizar_producto(
            company=self.company,
            user=self.user,
            product=self.product,
            default_price=Decimal("890"),
            origen="assistant",
        )

        entry = AuditLog.objects.get(entity_type="Product", entity_id=str(self.product.id))
        self.assertEqual(entry.source, AuditLog.Source.ASSISTANT)
