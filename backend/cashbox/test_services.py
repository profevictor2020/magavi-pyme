import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.factories import UserFactory
from audit.models import AuditLog
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory
from purchases.services import registrar_compra
from sales.services import crear_venta

from .models import CashMovement
from .services import (
    actualizar_gasto,
    consultar_gastos,
    get_cash_movement_or_raise,
    obtener_resumen,
    registrar_gasto,
)


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


class RegistrarGastoTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()

    def test_creates_expense_movement_with_category(self):
        movement = registrar_gasto(
            company=self.company, user=self.user, amount=Decimal("150000"), category="arriendo"
        )

        self.assertEqual(movement.type, CashMovement.MovementType.EXPENSE)
        self.assertEqual(movement.category, "arriendo")
        self.assertEqual(movement.amount, Decimal("150000.00"))
        self.assertEqual(movement.reference_type, CashMovement.ReferenceType.MANUAL)

    def test_shows_up_in_obtener_resumen_expense_total(self):
        registrar_gasto(
            company=self.company, user=self.user, amount=Decimal("20000"), category="servicios"
        )

        resumen = obtener_resumen(company=self.company)

        self.assertEqual(resumen["cash"]["today"]["expense"], "20000.00")

    def test_otro_category_requires_description(self):
        with self.assertRaises(ValidationError):
            registrar_gasto(
                company=self.company, user=self.user, amount=Decimal("5000"), category="otro"
            )

    def test_otro_category_with_description_is_allowed(self):
        movement = registrar_gasto(
            company=self.company,
            user=self.user,
            amount=Decimal("5000"),
            category="otro",
            description="Multa municipal",
        )

        self.assertEqual(movement.category, "otro")
        self.assertEqual(movement.description, "Multa municipal")

    def test_rejects_zero_or_negative_amount(self):
        with self.assertRaises(ValidationError):
            registrar_gasto(
                company=self.company, user=self.user, amount=Decimal("0"), category="sueldos"
            )

    def test_writes_audit_log(self):
        movement = registrar_gasto(
            company=self.company, user=self.user, amount=Decimal("30000"), category="sueldos"
        )

        entry = AuditLog.objects.get(entity_type="CashMovement", entity_id=str(movement.id))
        self.assertEqual(entry.action, "cashmovement.create")
        self.assertEqual(entry.source, AuditLog.Source.UI)

    def test_assistant_origin_maps_to_assistant_audit_source(self):
        movement = registrar_gasto(
            company=self.company,
            user=self.user,
            amount=Decimal("30000"),
            category="sueldos",
            origen="assistant",
        )

        entry = AuditLog.objects.get(entity_type="CashMovement", entity_id=str(movement.id))
        self.assertEqual(entry.source, AuditLog.Source.ASSISTANT)


class ActualizarGastoTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.gasto = registrar_gasto(
            company=self.company, user=self.user, amount=Decimal("150000"), category="arriendo"
        )

    def test_updates_only_the_given_field(self):
        movement = actualizar_gasto(
            company=self.company, user=self.user, cash_movement=self.gasto, amount=Decimal("140000")
        )

        self.assertEqual(movement.amount, Decimal("140000.00"))
        self.assertEqual(movement.category, "arriendo")

    def test_updates_category_and_description_together(self):
        movement = actualizar_gasto(
            company=self.company,
            user=self.user,
            cash_movement=self.gasto,
            category="servicios",
            description="Cuenta de luz reclasificada",
        )

        self.assertEqual(movement.category, "servicios")
        self.assertEqual(movement.description, "Cuenta de luz reclasificada")

    def test_rejects_call_with_no_fields_to_update(self):
        with self.assertRaises(ValidationError):
            actualizar_gasto(company=self.company, user=self.user, cash_movement=self.gasto)

    def test_rejects_zero_or_negative_amount(self):
        with self.assertRaises(ValidationError):
            actualizar_gasto(
                company=self.company,
                user=self.user,
                cash_movement=self.gasto,
                amount=Decimal("0"),
            )

    def test_changing_to_otro_without_description_is_rejected(self):
        with self.assertRaises(ValidationError):
            actualizar_gasto(
                company=self.company, user=self.user, cash_movement=self.gasto, category="otro"
            )

    def test_changing_to_otro_with_description_is_allowed(self):
        movement = actualizar_gasto(
            company=self.company,
            user=self.user,
            cash_movement=self.gasto,
            category="otro",
            description="Multa municipal",
        )

        self.assertEqual(movement.category, "otro")

    def test_rejects_correcting_a_purchase_generated_movement(self):
        product = ProductFactory(company=self.company, current_stock=Decimal("10"))
        registrar_compra(
            company=self.company,
            user=self.user,
            items=[{"product": product, "quantity": Decimal("5")}],
        )
        purchase_movement = (
            CashMovement.objects.for_company(self.company)
            .filter(reference_type=CashMovement.ReferenceType.PURCHASE)
            .get()
        )

        with self.assertRaises(ValidationError):
            actualizar_gasto(
                company=self.company,
                user=self.user,
                cash_movement=purchase_movement,
                amount=Decimal("1"),
            )

    def test_writes_audit_log_with_before_and_after(self):
        actualizar_gasto(
            company=self.company, user=self.user, cash_movement=self.gasto, amount=Decimal("140000")
        )

        entry = AuditLog.objects.get(
            entity_type="CashMovement", entity_id=str(self.gasto.id), action="cashmovement.update"
        )
        self.assertEqual(Decimal(entry.before["amount"]), Decimal("150000"))
        self.assertEqual(Decimal(entry.after["amount"]), Decimal("140000"))


class GetCashMovementOrRaiseTests(TestCase):
    def test_rejects_movement_from_another_company(self):
        company = CompanyFactory()
        other_company = CompanyFactory()
        user = UserFactory()
        gasto = registrar_gasto(
            company=other_company,
            user=user,
            amount=Decimal("1000"),
            category="otro",
            description="x",
        )

        with self.assertRaises(ValidationError):
            get_cash_movement_or_raise(company=company, cash_movement_id=gasto.id)


class ConsultarGastosTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()

    def test_empty_when_nothing_registered(self):
        self.assertEqual(consultar_gastos(company=self.company), [])

    def test_lists_manual_expenses_most_recent_first(self):
        primero = registrar_gasto(
            company=self.company, user=self.user, amount=Decimal("150000"), category="arriendo"
        )
        segundo = registrar_gasto(
            company=self.company, user=self.user, amount=Decimal("30000"), category="sueldos"
        )

        resultado = consultar_gastos(company=self.company)

        self.assertEqual(resultado[0]["id"], segundo.id)
        self.assertEqual(resultado[1]["id"], primero.id)

    def test_excludes_sales_and_purchases(self):
        product = ProductFactory(company=self.company, current_stock=Decimal("10"))
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": product, "quantity": Decimal("1")}],
        )

        self.assertEqual(consultar_gastos(company=self.company), [])

    def test_excludes_other_companies_expenses(self):
        other_company = CompanyFactory()
        other_user = UserFactory()
        registrar_gasto(
            company=other_company, user=other_user, amount=Decimal("1000"), category="sueldos"
        )

        self.assertEqual(consultar_gastos(company=self.company), [])

    def _gasto_en_fecha(self, created_at, amount=Decimal("1000")):
        # registrar_gasto siempre usa "ahora" (auto_now_add); para probar
        # filtrado por período hay que retrasar el gasto después de
        # creado (ver el mismo patrón en ObtenerResumenTests arriba).
        gasto = registrar_gasto(
            company=self.company, user=self.user, amount=amount, category="otro", description="x"
        )
        CashMovement.objects.filter(pk=gasto.id).update(created_at=created_at)
        return gasto

    def test_period_mes_excluye_gastos_de_meses_anteriores(self):
        # Bug real reportado en vivo: "qué gastos llevamos este mes" no
        # filtraba de verdad por mes, solo mostraba los últimos N gastos
        # sin importar cuándo fueron — funcionaba por casualidad mientras
        # todos los datos de prueba eran del mismo día (ver ADR-022).
        mes_pasado = timezone.localtime().replace(day=1) - timezone.timedelta(days=1)
        gasto_viejo = self._gasto_en_fecha(mes_pasado)
        gasto_de_este_mes = registrar_gasto(
            company=self.company,
            user=self.user,
            amount=Decimal("2000"),
            category="otro",
            description="y",
        )

        resultado = consultar_gastos(company=self.company, period="mes")

        ids = [g["id"] for g in resultado]
        self.assertIn(gasto_de_este_mes.id, ids)
        self.assertNotIn(gasto_viejo.id, ids)

    def test_period_total_incluye_todo_el_historico(self):
        hace_un_anio = timezone.localtime() - timezone.timedelta(days=400)
        gasto_viejo = self._gasto_en_fecha(hace_un_anio)

        resultado = consultar_gastos(company=self.company, period="total")

        self.assertIn(gasto_viejo.id, [g["id"] for g in resultado])

    def test_rango_de_fechas_explicito(self):
        dentro_del_rango = self._gasto_en_fecha(
            timezone.localtime().replace(year=2025, month=8, day=10)
        )
        fuera_del_rango = self._gasto_en_fecha(
            timezone.localtime().replace(year=2025, month=9, day=1)
        )

        resultado = consultar_gastos(
            company=self.company,
            date_from=datetime.date(2025, 8, 1),
            date_to=datetime.date(2025, 8, 31),
        )

        ids = [g["id"] for g in resultado]
        self.assertIn(dentro_del_rango.id, ids)
        self.assertNotIn(fuera_del_rango.id, ids)

    def test_sin_period_ni_fechas_no_filtra_como_antes(self):
        # Comportamiento previo a ADR-022 preservado: sin period/fechas,
        # consultar_gastos no filtra por fecha.
        viejo = self._gasto_en_fecha(timezone.localtime() - timezone.timedelta(days=400))

        resultado = consultar_gastos(company=self.company)

        self.assertIn(viejo.id, [g["id"] for g in resultado])
