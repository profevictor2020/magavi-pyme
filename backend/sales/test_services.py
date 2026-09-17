import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.factories import UserFactory
from cashbox.models import CashMovement
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory
from inventory.models import InventoryMovement

from .models import Sale
from .services import (
    consultar_ventas_periodo,
    consultar_ventas_producto,
    crear_venta,
    productos_mas_vendidos,
)


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


class ConsultarVentasProductoTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(
            company=self.company, default_price=Decimal("2500.00"), current_stock=Decimal("10")
        )

    def test_zero_when_nothing_sold(self):
        resultado = consultar_ventas_producto(company=self.company, product=self.product)

        self.assertEqual(resultado["product_id"], self.product.id)
        self.assertEqual(resultado["today"], {"quantity": "0.000", "total": "0.00"})
        self.assertEqual(resultado["week"], {"quantity": "0.000", "total": "0.00"})

    def test_sums_quantity_and_total_of_multiple_sales(self):
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("3")}],
        )
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("2")}],
        )

        resultado = consultar_ventas_producto(company=self.company, product=self.product)

        self.assertEqual(resultado["today"]["quantity"], "5.000")
        self.assertEqual(resultado["today"]["total"], "12500.00")
        self.assertEqual(resultado["week"]["quantity"], "5.000")

    def test_ignores_sales_of_other_products(self):
        other_product = ProductFactory(company=self.company, current_stock=Decimal("10"))
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": other_product, "quantity": Decimal("4")}],
        )

        resultado = consultar_ventas_producto(company=self.company, product=self.product)

        self.assertEqual(resultado["today"]["quantity"], "0.000")

    def test_ignores_sales_from_other_companies(self):
        other_company = CompanyFactory()
        other_user = UserFactory()
        foreign_product = ProductFactory(company=other_company, current_stock=Decimal("10"))
        crear_venta(
            company=other_company,
            user=other_user,
            items=[{"product": foreign_product, "quantity": Decimal("9")}],
        )

        resultado = consultar_ventas_producto(company=self.company, product=self.product)

        self.assertEqual(resultado["today"]["quantity"], "0.000")


class ProductosMasVendidosTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()

    def test_empty_when_nothing_sold(self):
        self.assertEqual(productos_mas_vendidos(company=self.company), [])

    def test_orders_by_quantity_sold_descending(self):
        goma = ProductFactory(company=self.company, name="Goma", current_stock=Decimal("100"))
        lapiz = ProductFactory(company=self.company, name="Lápiz", current_stock=Decimal("100"))
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": goma, "quantity": Decimal("3")}],
        )
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": lapiz, "quantity": Decimal("10")}],
        )

        resultado = productos_mas_vendidos(company=self.company)

        self.assertEqual(resultado[0]["product_name"], "Lápiz")
        self.assertEqual(resultado[0]["quantity"], "10.000")
        self.assertEqual(resultado[1]["product_name"], "Goma")

    def test_sums_quantity_across_multiple_sales_of_same_product(self):
        goma = ProductFactory(company=self.company, name="Goma", current_stock=Decimal("100"))
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": goma, "quantity": Decimal("3")}],
        )
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": goma, "quantity": Decimal("2")}],
        )

        resultado = productos_mas_vendidos(company=self.company)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["quantity"], "5.000")
        self.assertEqual(resultado[0]["total"], "5000.00")

    def test_ignores_sales_from_other_companies(self):
        other_company = CompanyFactory()
        other_user = UserFactory()
        foreign_product = ProductFactory(company=other_company, current_stock=Decimal("10"))
        crear_venta(
            company=other_company,
            user=other_user,
            items=[{"product": foreign_product, "quantity": Decimal("9")}],
        )

        self.assertEqual(productos_mas_vendidos(company=self.company), [])


class ConsultarVentasPeriodoTests(TestCase):
    """Ver docs/DECISIONS.md ADR-022: a diferencia de consultar_ventas
    (siempre hoy/semana), esta cubre preguntas históricas — "¿cuánto
    llevo vendido en total?", "ventas de este año", "ventas de agosto"."""

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(company=self.company, current_stock=Decimal("100"))

    def _venta_en_fecha(self, sold_at, quantity=Decimal("1")):
        # sold_at es auto_now_add: se retrasa después de creada la venta,
        # mismo patrón que en cashbox/test_services.py.
        venta = crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": quantity}],
        )
        Sale.objects.filter(pk=venta.id).update(sold_at=sold_at)
        return venta

    def test_sin_argumentos_equivale_a_total_todo_el_historico(self):
        self._venta_en_fecha(timezone.localtime() - timezone.timedelta(days=400))

        resultado = consultar_ventas_periodo(company=self.company)

        self.assertEqual(resultado["period"], "total")
        self.assertEqual(resultado["count"], 1)

    def test_period_mes_excluye_ventas_de_meses_anteriores(self):
        mes_pasado = timezone.localtime().replace(day=1) - timezone.timedelta(days=1)
        self._venta_en_fecha(mes_pasado)
        self._venta_en_fecha(timezone.localtime())

        resultado = consultar_ventas_periodo(company=self.company, period="mes")

        self.assertEqual(resultado["count"], 1)

    def test_period_anio_excluye_ventas_de_anios_anteriores(self):
        hace_dos_anios = timezone.localtime().replace(year=timezone.localtime().year - 2)
        self._venta_en_fecha(hace_dos_anios)
        self._venta_en_fecha(timezone.localtime())

        resultado = consultar_ventas_periodo(company=self.company, period="anio")

        self.assertEqual(resultado["count"], 1)

    def test_rango_de_fechas_explicito(self):
        self._venta_en_fecha(timezone.localtime().replace(year=2025, month=8, day=10))
        self._venta_en_fecha(timezone.localtime().replace(year=2025, month=9, day=1))

        resultado = consultar_ventas_periodo(
            company=self.company,
            date_from=datetime.date(2025, 8, 1),
            date_to=datetime.date(2025, 8, 31),
        )

        self.assertEqual(resultado["count"], 1)

    def test_solo_cuenta_ventas_confirmadas_de_esta_empresa(self):
        other_company = CompanyFactory()
        other_user = UserFactory()
        other_product = ProductFactory(company=other_company, current_stock=Decimal("10"))
        crear_venta(
            company=other_company,
            user=other_user,
            items=[{"product": other_product, "quantity": Decimal("5")}],
        )

        resultado = consultar_ventas_periodo(company=self.company)

        self.assertEqual(resultado["count"], 0)
        self.assertEqual(resultado["total"], "0.00")
