from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.factories import UserFactory
from cashbox.models import CashMovement
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory
from inventory.models import InventoryMovement

from .models import Sale
from .services import crear_venta


class CrearVentaTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(
            company=self.company,
            default_price=Decimal("2500.00"),
            current_stock=Decimal("10"),
        )

    def test_creates_sale_with_correct_total(self):
        sale = crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("3")}],
        )

        self.assertEqual(sale.total, Decimal("7500.00"))
        self.assertEqual(sale.items.count(), 1)
        item = sale.items.first()
        self.assertEqual(item.unit_price, Decimal("2500.00"))
        self.assertEqual(item.subtotal, Decimal("7500.00"))

    def test_uses_explicit_unit_price_when_given(self):
        sale = crear_venta(
            company=self.company,
            user=self.user,
            items=[
                {"product": self.product, "quantity": Decimal("2"), "unit_price": Decimal("2000")}
            ],
        )

        self.assertEqual(sale.total, Decimal("4000.00"))

    def test_decreases_product_stock(self):
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("4")}],
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("6.000"))

    def test_creates_out_inventory_movement_linked_to_sale(self):
        sale = crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("1")}],
        )

        movement = InventoryMovement.objects.for_company(self.company).get(
            product=self.product, reference_type=InventoryMovement.ReferenceType.SALE
        )
        self.assertEqual(movement.type, InventoryMovement.MovementType.OUT)
        self.assertEqual(movement.quantity, Decimal("-1.000"))
        self.assertEqual(movement.reference_id, sale.id)

    def test_creates_income_cash_movement(self):
        sale = crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("1")}],
        )

        movement = CashMovement.objects.for_company(self.company).get(reference_id=sale.id)
        self.assertEqual(movement.type, CashMovement.MovementType.INCOME)
        self.assertEqual(movement.amount, sale.total)
        self.assertEqual(movement.reference_type, CashMovement.ReferenceType.SALE)

    def test_rejects_sale_without_items(self):
        with self.assertRaises(ValidationError):
            crear_venta(company=self.company, user=self.user, items=[])

    def test_rejects_when_insufficient_stock(self):
        with self.assertRaises(ValidationError):
            crear_venta(
                company=self.company,
                user=self.user,
                items=[{"product": self.product, "quantity": Decimal("999")}],
            )

    def test_atomicity_no_orphan_sale_when_an_item_fails(self):
        sales_before = Sale.objects.for_company(self.company).count()
        other_product = ProductFactory(company=self.company, current_stock=Decimal("1"))

        with self.assertRaises(ValidationError):
            crear_venta(
                company=self.company,
                user=self.user,
                items=[
                    {"product": self.product, "quantity": Decimal("1")},
                    {"product": other_product, "quantity": Decimal("999")},
                ],
            )

        self.assertEqual(Sale.objects.for_company(self.company).count(), sales_before)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("10.000"))
        self.assertEqual(
            InventoryMovement.objects.for_company(self.company)
            .filter(product=self.product)
            .count(),
            0,
        )
        self.assertEqual(CashMovement.objects.for_company(self.company).count(), 0)

    def test_rejects_product_from_another_company(self):
        other_company = CompanyFactory()
        foreign_product = ProductFactory(company=other_company)

        with self.assertRaises(ValidationError):
            crear_venta(
                company=self.company,
                user=self.user,
                items=[{"product": foreign_product, "quantity": Decimal("1")}],
            )
