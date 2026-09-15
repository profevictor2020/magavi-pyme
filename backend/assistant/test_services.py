from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.factories import UserFactory
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory
from inventory.models import InventoryMovement
from sales.models import Sale

from .models import PendingAction
from .services import cancelar_intent, confirmar_intent, proponer_intent


class ProponerIntentTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(
            company=self.company, default_price=Decimal("2500.00"), current_stock=Decimal("10")
        )

    def test_mutating_intent_creates_pending_action_without_executing(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="crear_venta",
            raw_parameters={"items": [{"product_id": self.product.id, "quantity": "3"}]},
        )

        self.assertEqual(resultado["status"], "pending_confirmation")
        pending = PendingAction.objects.for_company(self.company).get(
            pk=resultado["pending_action_id"]
        )
        self.assertEqual(pending.status, PendingAction.Status.PENDING)
        self.assertEqual(pending.intent_name, "crear_venta")
        self.assertEqual(Sale.objects.for_company(self.company).count(), 0)

    def test_readonly_intent_executes_immediately(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_stock_bajo",
            raw_parameters={},
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"], [])
        self.assertEqual(PendingAction.objects.for_company(self.company).count(), 0)

    def test_consultar_ventas_matches_sales_summary(self):
        resultado = proponer_intent(
            company=self.company, user=self.user, intent_name="consultar_ventas", raw_parameters={}
        )

        self.assertEqual(resultado["result"]["today"], {"total": "0.00", "count": 0})

    def test_unknown_intent_is_rejected(self):
        with self.assertRaises(ValidationError):
            proponer_intent(
                company=self.company, user=self.user, intent_name="borrar_todo", raw_parameters={}
            )

    def test_invalid_parameters_are_rejected(self):
        with self.assertRaises(Exception):
            proponer_intent(
                company=self.company,
                user=self.user,
                intent_name="crear_venta",
                raw_parameters={"items": []},
            )


class ConfirmarIntentTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(
            company=self.company, default_price=Decimal("2500.00"), current_stock=Decimal("10")
        )

    def _proponer_venta(self, quantity="3"):
        return proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="crear_venta",
            raw_parameters={"items": [{"product_id": self.product.id, "quantity": quantity}]},
        )

    def test_confirm_executes_the_tool_layer(self):
        propuesta = self._proponer_venta()

        sale = confirmar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        self.assertEqual(sale.total, Decimal("7500.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("7.000"))

        pending = PendingAction.objects.for_company(self.company).get(
            pk=propuesta["pending_action_id"]
        )
        self.assertEqual(pending.status, PendingAction.Status.CONFIRMED)
        self.assertIsNotNone(pending.resolved_at)

    def test_double_confirm_is_rejected_and_does_not_duplicate(self):
        propuesta = self._proponer_venta()
        confirmar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        with self.assertRaises(ValidationError):
            confirmar_intent(
                company=self.company,
                user=self.user,
                pending_action_id=propuesta["pending_action_id"],
            )

        self.assertEqual(Sale.objects.for_company(self.company).count(), 1)

    def test_confirming_expired_action_raises_and_marks_expired(self):
        propuesta = self._proponer_venta()
        PendingAction.objects.filter(pk=propuesta["pending_action_id"]).update(
            expires_at=timezone.now() - timezone.timedelta(minutes=1)
        )

        with self.assertRaises(ValidationError):
            confirmar_intent(
                company=self.company,
                user=self.user,
                pending_action_id=propuesta["pending_action_id"],
            )

        pending = PendingAction.objects.for_company(self.company).get(
            pk=propuesta["pending_action_id"]
        )
        self.assertEqual(pending.status, PendingAction.Status.EXPIRED)
        self.assertEqual(Sale.objects.for_company(self.company).count(), 0)

    def test_confirm_revalidates_state_and_fails_if_stock_now_insufficient(self):
        propuesta = self._proponer_venta(quantity="8")
        # El stock cambió entre la propuesta y la confirmación (ej. se
        # registró otra venta mientras tanto).
        self.product.current_stock = Decimal("2")
        self.product.save(update_fields=["current_stock"])

        with self.assertRaises(ValidationError):
            confirmar_intent(
                company=self.company,
                user=self.user,
                pending_action_id=propuesta["pending_action_id"],
            )

        self.assertEqual(Sale.objects.for_company(self.company).count(), 0)
        pending = PendingAction.objects.for_company(self.company).get(
            pk=propuesta["pending_action_id"]
        )
        self.assertEqual(pending.status, PendingAction.Status.PENDING)

    def test_confirm_nonexistent_pending_action_raises(self):
        with self.assertRaises(ValidationError):
            confirmar_intent(company=self.company, user=self.user, pending_action_id=999999)

    def test_cannot_confirm_another_users_pending_action(self):
        propuesta = self._proponer_venta()
        other_user = UserFactory()

        with self.assertRaises(ValidationError):
            confirmar_intent(
                company=self.company,
                user=other_user,
                pending_action_id=propuesta["pending_action_id"],
            )

    def test_registrar_compra_intent_end_to_end(self):
        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="registrar_compra",
            raw_parameters={"items": [{"product_id": self.product.id, "quantity": "20"}]},
        )

        purchase = confirmar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("30.000"))
        self.assertEqual(purchase.total, purchase.items.first().subtotal)

    def test_ajustar_inventario_intent_end_to_end(self):
        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="ajustar_inventario",
            raw_parameters={"product_id": self.product.id, "cantidad": "-2", "motivo": "Merma"},
        )

        movement = confirmar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        self.assertEqual(movement.type, InventoryMovement.MovementType.ADJUSTMENT)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("8.000"))


class CancelarIntentTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(company=self.company, current_stock=Decimal("10"))

    def _proponer_venta(self):
        return proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="crear_venta",
            raw_parameters={"items": [{"product_id": self.product.id, "quantity": "1"}]},
        )

    def test_cancel_marks_action_cancelled(self):
        propuesta = self._proponer_venta()

        pending = cancelar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        self.assertEqual(pending.status, PendingAction.Status.CANCELLED)

    def test_cannot_confirm_a_cancelled_action(self):
        propuesta = self._proponer_venta()
        cancelar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        with self.assertRaises(ValidationError):
            confirmar_intent(
                company=self.company,
                user=self.user,
                pending_action_id=propuesta["pending_action_id"],
            )


class SeguridadIntentTests(TestCase):
    """Un intent que referencia un producto/empresa ajena debe ser
    rechazado (ver docs/ROADMAP.md Fase 7, docs/SECURITY.md #5)."""

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.other_company = CompanyFactory()
        self.foreign_product = ProductFactory(
            company=self.other_company, current_stock=Decimal("10")
        )

    def test_crear_venta_rejects_product_from_another_company(self):
        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="crear_venta",
            raw_parameters={"items": [{"product_id": self.foreign_product.id, "quantity": "1"}]},
        )

        with self.assertRaises(ValidationError):
            confirmar_intent(
                company=self.company,
                user=self.user,
                pending_action_id=propuesta["pending_action_id"],
            )

    def test_ajustar_inventario_rejects_product_from_another_company(self):
        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="ajustar_inventario",
            raw_parameters={"product_id": self.foreign_product.id, "cantidad": "5", "motivo": "x"},
        )

        with self.assertRaises(ValidationError):
            confirmar_intent(
                company=self.company,
                user=self.user,
                pending_action_id=propuesta["pending_action_id"],
            )
