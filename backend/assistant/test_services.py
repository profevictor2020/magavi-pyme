from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from accounts.factories import UserFactory
from cashbox.models import CashMovement
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

    def test_registrar_gasto_creates_pending_action_without_executing(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="registrar_gasto",
            raw_parameters={"amount": "20000", "category": "servicios"},
        )

        self.assertEqual(resultado["status"], "pending_confirmation")
        self.assertEqual(CashMovement.objects.for_company(self.company).count(), 0)

    def test_registrar_gasto_otro_sin_descripcion_es_rechazado(self):
        # Falla en la validación del serializer del intent (antes de crear
        # la PendingAction), que lanza el ValidationError de DRF — no el
        # de Django que lanza el Tool Layer si se lo llama directo (ver
        # cashbox/test_services.py::RegistrarGastoTests).
        with self.assertRaises(DRFValidationError):
            proponer_intent(
                company=self.company,
                user=self.user,
                intent_name="registrar_gasto",
                raw_parameters={"amount": "5000", "category": "otro"},
            )

    def test_consultar_gastos_executes_immediately(self):
        resultado = proponer_intent(
            company=self.company, user=self.user, intent_name="consultar_gastos", raw_parameters={}
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"], [])

    def test_actualizar_gasto_creates_pending_action_without_executing(self):
        gasto = CashMovement.objects.create(
            company=self.company,
            type=CashMovement.MovementType.EXPENSE,
            amount=Decimal("150000"),
            reference_type=CashMovement.ReferenceType.MANUAL,
            category=CashMovement.Category.ARRIENDO,
            created_by=self.user,
        )

        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="actualizar_gasto",
            raw_parameters={"cash_movement_id": gasto.id, "amount": "140000"},
        )

        self.assertEqual(resultado["status"], "pending_confirmation")
        gasto.refresh_from_db()
        self.assertEqual(gasto.amount, Decimal("150000.00"))

    def test_actualizar_gasto_propuesta_de_otra_empresa_se_crea_pero_no_se_puede_confirmar(self):
        # Mismo patrón que ajustar_inventario/crear_venta con un
        # producto ajeno (ver SeguridadIntentTests más abajo): la
        # propuesta es válida en forma, pero confirmarla revalida contra
        # el Tool Layer y ahí sí se rechaza (docs/ARCHITECTURE.md #3.4).
        other_company = CompanyFactory()
        gasto_ajeno = CashMovement.objects.create(
            company=other_company,
            type=CashMovement.MovementType.EXPENSE,
            amount=Decimal("1000"),
            reference_type=CashMovement.ReferenceType.MANUAL,
            category=CashMovement.Category.SUELDOS,
            created_by=self.user,
        )

        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="actualizar_gasto",
            raw_parameters={"cash_movement_id": gasto_ajeno.id, "amount": "1"},
        )

        self.assertEqual(propuesta["status"], "pending_confirmation")
        with self.assertRaises(ValidationError):
            confirmar_intent(
                company=self.company,
                user=self.user,
                pending_action_id=propuesta["pending_action_id"],
            )

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

    def test_consultar_ventas_producto_executes_immediately(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_ventas_producto",
            raw_parameters={"product_id": self.product.id},
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"]["product_id"], self.product.id)
        self.assertEqual(resultado["result"]["today"], {"quantity": "0.000", "total": "0.00"})

    def test_consultar_ventas_producto_de_otra_empresa_es_rechazado(self):
        other_company = CompanyFactory()
        foreign_product = ProductFactory(company=other_company)

        with self.assertRaises(ValidationError):
            proponer_intent(
                company=self.company,
                user=self.user,
                intent_name="consultar_ventas_producto",
                raw_parameters={"product_id": foreign_product.id},
            )

    def test_consultar_ventas_periodo_executes_immediately(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_ventas_periodo",
            raw_parameters={},
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"]["period"], "total")
        self.assertEqual(resultado["result"]["count"], 0)

    def test_consultar_ventas_periodo_acepta_period_con_nombre(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_ventas_periodo",
            raw_parameters={"period": "mes"},
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"]["period"], "mes")

    def test_consultar_ventas_periodo_rechaza_period_invalido(self):
        with self.assertRaises(DRFValidationError):
            proponer_intent(
                company=self.company,
                user=self.user,
                intent_name="consultar_ventas_periodo",
                raw_parameters={"period": "no_existe"},
            )

    def test_consultar_gastos_acepta_period(self):
        # Bug real (ver docs/DECISIONS.md ADR-022): antes consultar_gastos
        # no filtraba por fecha en absoluto, así que "este mes" no era
        # realmente "este mes" — funcionaba por casualidad con datos de
        # prueba todos del mismo día.
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_gastos",
            raw_parameters={"period": "mes"},
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"], [])

    def test_consultar_detalle_ventas_executes_immediately(self):
        # Ver docs/DECISIONS.md ADR-026: "detállame esas ventas" cayó en
        # no_entendido porque no existía un intent para el detalle por
        # venta (solo el total agregado, consultar_ventas_periodo).
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_detalle_ventas",
            raw_parameters={},
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"], [])

    def test_consultar_detalle_ventas_acepta_period(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_detalle_ventas",
            raw_parameters={"period": "mes"},
        )

        self.assertEqual(resultado["status"], "executed")

    def test_consultar_productos_mas_vendidos_executes_immediately(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_productos_mas_vendidos",
            raw_parameters={},
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"], [])

    def test_consultar_producto_executes_immediately(self):
        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_producto",
            raw_parameters={"product_id": self.product.id},
        )

        self.assertEqual(resultado["status"], "executed")
        self.assertEqual(resultado["result"], {
            "id": self.product.id,
            "name": self.product.name,
            "unit": self.product.unit,
            "current_stock": "10.000",
            "low_stock_threshold": "0.000",
            "default_price": "2500.00",
        })

    def test_consultar_producto_de_otra_empresa_es_rechazado(self):
        other_company = CompanyFactory()
        foreign_product = ProductFactory(company=other_company)

        with self.assertRaises(ValidationError):
            proponer_intent(
                company=self.company,
                user=self.user,
                intent_name="consultar_producto",
                raw_parameters={"product_id": foreign_product.id},
            )

    def test_consultar_catalogo_lista_solo_productos_de_la_empresa(self):
        other_company = CompanyFactory()
        ProductFactory(company=other_company, name="Ajeno")

        resultado = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="consultar_catalogo",
            raw_parameters={},
        )

        self.assertEqual(resultado["status"], "executed")
        nombres = [item["name"] for item in resultado["result"]]
        self.assertEqual(nombres, [self.product.name])

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

    def test_confirm_crear_producto_creates_it_with_initial_stock(self):
        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="crear_producto",
            raw_parameters={"name": "Café molido", "initial_stock": "5"},
        )

        product = confirmar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        self.assertEqual(product.name, "Café molido")
        self.assertEqual(product.current_stock, Decimal("5.000"))

    def test_confirm_actualizar_producto_updates_the_price(self):
        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="actualizar_producto",
            raw_parameters={"product_id": self.product.id, "default_price": "890"},
        )

        product = confirmar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        self.assertEqual(product.default_price, Decimal("890.00"))
        self.assertEqual(product.current_stock, Decimal("10.000"))

    def test_confirm_registrar_gasto_creates_the_expense(self):
        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="registrar_gasto",
            raw_parameters={"amount": "150000", "category": "arriendo"},
        )

        movement = confirmar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        self.assertEqual(movement.amount, Decimal("150000.00"))
        self.assertEqual(movement.category, "arriendo")

    def test_confirm_actualizar_gasto_corrects_the_amount(self):
        gasto = CashMovement.objects.create(
            company=self.company,
            type=CashMovement.MovementType.EXPENSE,
            amount=Decimal("150000"),
            reference_type=CashMovement.ReferenceType.MANUAL,
            category=CashMovement.Category.ARRIENDO,
            created_by=self.user,
        )
        propuesta = proponer_intent(
            company=self.company,
            user=self.user,
            intent_name="actualizar_gasto",
            raw_parameters={"cash_movement_id": gasto.id, "amount": "140000"},
        )

        movement = confirmar_intent(
            company=self.company, user=self.user, pending_action_id=propuesta["pending_action_id"]
        )

        self.assertEqual(movement.amount, Decimal("140000.00"))

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
