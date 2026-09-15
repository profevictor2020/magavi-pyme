from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.factories import UserFactory
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory
from sales.services import crear_venta

from .models import CashMovement
from .services import obtener_resumen


class ObtenerResumenTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()

    def _cash_movement(self, movement_type, amount, created_at=None):
        movement = CashMovement.objects.create(
            company=self.company,
            type=movement_type,
            amount=amount,
            description="test",
            created_by=self.user,
        )
        if created_at is not None:
            # auto_now_add solo aplica en INSERT; .update() lo evita, lo
            # que permite simular movimientos de otros momentos para
            # probar los límites de fecha.
            CashMovement.objects.filter(pk=movement.pk).update(created_at=created_at)
        return movement

    def test_cash_today_reflects_income_and_expense(self):
        self._cash_movement(CashMovement.MovementType.INCOME, Decimal("10000"))
        self._cash_movement(CashMovement.MovementType.EXPENSE, Decimal("4000"))

        resumen = obtener_resumen(company=self.company)

        self.assertEqual(resumen["cash"]["today"]["income"], "10000.00")
        self.assertEqual(resumen["cash"]["today"]["expense"], "4000.00")
        self.assertEqual(resumen["cash"]["today"]["balance"], "6000.00")

    def test_movement_from_yesterday_excluded_from_today(self):
        yesterday = timezone.localtime() - timezone.timedelta(days=1)
        self._cash_movement(CashMovement.MovementType.INCOME, Decimal("5000"), created_at=yesterday)

        resumen = obtener_resumen(company=self.company)

        self.assertEqual(resumen["cash"]["today"]["income"], "0.00")

    def test_late_night_chile_movement_still_counts_as_today(self):
        # 23:30 hora de Chile (America/Santiago, UTC-3/-4) es ya el día
        # siguiente en UTC. Si el cálculo usara límites de día en UTC en
        # vez de hora local, este movimiento se contaría mal.
        near_midnight_local = timezone.localtime().replace(
            hour=23, minute=30, second=0, microsecond=0
        )
        self._cash_movement(
            CashMovement.MovementType.INCOME, Decimal("7000"), created_at=near_midnight_local
        )

        resumen = obtener_resumen(company=self.company)

        self.assertEqual(resumen["cash"]["today"]["income"], "7000.00")

    def test_sales_today_matches_sale_total(self):
        product = ProductFactory(
            company=self.company, default_price=Decimal("1000.00"), current_stock=Decimal("10")
        )
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": product, "quantity": Decimal("2")}],
        )

        resumen = obtener_resumen(company=self.company)

        self.assertEqual(resumen["sales"]["today"]["total"], "2000.00")
        self.assertEqual(resumen["sales"]["today"]["count"], 1)
        # crear_venta ya genera el CashMovement de ingreso correspondiente.
        self.assertEqual(resumen["cash"]["today"]["income"], "2000.00")

    def test_includes_low_stock_products_only(self):
        low = ProductFactory(
            company=self.company,
            name="Bajo stock",
            current_stock=Decimal("1"),
            low_stock_threshold=Decimal("5"),
        )
        ProductFactory(
            company=self.company,
            name="Stock ok",
            current_stock=Decimal("50"),
            low_stock_threshold=Decimal("5"),
        )

        resumen = obtener_resumen(company=self.company)

        names = [p["name"] for p in resumen["low_stock_products"]]
        self.assertIn(low.name, names)
        self.assertNotIn("Stock ok", names)

    def test_empty_company_has_zeroed_summary(self):
        resumen = obtener_resumen(company=self.company)

        self.assertEqual(
            resumen["cash"]["today"], {"income": "0.00", "expense": "0.00", "balance": "0.00"}
        )
        self.assertEqual(resumen["sales"]["today"], {"total": "0.00", "count": 0})
        self.assertEqual(resumen["low_stock_products"], [])
