from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.factories import UserFactory
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory

from .models import InventoryMovement
from .services import ajustar_inventario


class AjustarInventarioTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(company=self.company, current_stock=Decimal("10"))

    def test_positive_adjustment_increases_stock(self):
        movement = ajustar_inventario(
            company=self.company,
            user=self.user,
            product=self.product,
            cantidad=Decimal("5"),
            motivo="Recepcion de mercaderia",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("15.000"))
        self.assertEqual(movement.balance_after, Decimal("15.000"))
        self.assertEqual(movement.type, InventoryMovement.MovementType.ADJUSTMENT)

    def test_negative_adjustment_decreases_stock(self):
        ajustar_inventario(
            company=self.company,
            user=self.user,
            product=self.product,
            cantidad=Decimal("-4"),
            motivo="Merma",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("6.000"))

    def test_adjustment_cannot_leave_stock_negative(self):
        with self.assertRaises(ValidationError):
            ajustar_inventario(
                company=self.company,
                user=self.user,
                product=self.product,
                cantidad=Decimal("-100"),
                motivo="Merma excesiva",
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("10.000"))

    def test_zero_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            ajustar_inventario(
                company=self.company,
                user=self.user,
                product=self.product,
                cantidad=Decimal("0"),
                motivo="Sin cambio",
            )

    def test_product_from_another_company_is_rejected(self):
        other_company = CompanyFactory()

        with self.assertRaises(ValidationError):
            ajustar_inventario(
                company=other_company,
                user=self.user,
                product=self.product,
                cantidad=Decimal("1"),
                motivo="Cruzado",
            )

    def test_creates_auditable_movement_record(self):
        movement = ajustar_inventario(
            company=self.company,
            user=self.user,
            product=self.product,
            cantidad=Decimal("2"),
            motivo="Conteo fisico",
        )

        stored = InventoryMovement.objects.for_company(self.company).get(pk=movement.pk)
        self.assertEqual(stored.reason, "Conteo fisico")
        self.assertEqual(stored.created_by, self.user)
        self.assertEqual(stored.reference_type, InventoryMovement.ReferenceType.MANUAL)
