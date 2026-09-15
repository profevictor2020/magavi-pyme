from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.factories import UserFactory
from cashbox.models import CashMovement
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory
from inventory.models import InventoryMovement

from .models import Purchase
from .services import registrar_compra


class RegistrarCompraTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(
            company=self.company,
            default_cost=Decimal("1500.00"),
            current_stock=Decimal("5"),
        )

    def test_creates_purchase_with_correct_total(self):
        purchase = registrar_compra(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("10")}],
        )

        self.assertEqual(purchase.total, Decimal("15000.00"))
        self.assertEqual(purchase.items.count(), 1)
        item = purchase.items.first()
        self.assertEqual(item.unit_cost, Decimal("1500.00"))
        self.assertEqual(item.subtotal, Decimal("15000.00"))

    def test_uses_explicit_unit_cost_when_given(self):
        purchase = registrar_compra(
            company=self.company,
            user=self.user,
            items=[
                {"product": self.product, "quantity": Decimal("2"), "unit_cost": Decimal("1000")}
            ],
        )

        self.assertEqual(purchase.total, Decimal("2000.00"))

    def test_increases_product_stock(self):
        registrar_compra(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("20")}],
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("25.000"))

    def test_creates_in_inventory_movement_linked_to_purchase(self):
        purchase = registrar_compra(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("3")}],
        )

        movement = InventoryMovement.objects.for_company(self.company).get(
            product=self.product, reference_type=InventoryMovement.ReferenceType.PURCHASE
        )
        self.assertEqual(movement.type, InventoryMovement.MovementType.IN)
        self.assertEqual(movement.quantity, Decimal("3.000"))
        self.assertEqual(movement.reference_id, purchase.id)

    def test_creates_expense_cash_movement(self):
        purchase = registrar_compra(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("1")}],
        )

        movement = CashMovement.objects.for_company(self.company).get(reference_id=purchase.id)
        self.assertEqual(movement.type, CashMovement.MovementType.EXPENSE)
        self.assertEqual(movement.amount, purchase.total)
        self.assertEqual(movement.reference_type, CashMovement.ReferenceType.PURCHASE)

    def test_rejects_purchase_without_items(self):
        with self.assertRaises(ValidationError):
            registrar_compra(company=self.company, user=self.user, items=[])

    def test_atomicity_no_orphan_purchase_when_an_item_fails(self):
        purchases_before = Purchase.objects.for_company(self.company).count()
        other_company = CompanyFactory()
        foreign_product = ProductFactory(company=other_company)

        with self.assertRaises(ValidationError):
            registrar_compra(
                company=self.company,
                user=self.user,
                items=[
                    {"product": self.product, "quantity": Decimal("1")},
                    {"product": foreign_product, "quantity": Decimal("1")},
                ],
            )

        self.assertEqual(Purchase.objects.for_company(self.company).count(), purchases_before)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("5.000"))
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
            registrar_compra(
                company=self.company,
                user=self.user,
                items=[{"product": foreign_product, "quantity": Decimal("1")}],
            )
