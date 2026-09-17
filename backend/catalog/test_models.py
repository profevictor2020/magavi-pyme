from decimal import Decimal

from django.test import SimpleTestCase

from .models import Product, formatear_cantidad


class FormatearCantidadTests(SimpleTestCase):
    """Ver docs/DECISIONS.md ADR-024: el stock/las cantidades vendidas se
    guardan con 3 decimales (soportan kg/lt fraccionarios), pero eso no
    debería filtrarse tal cual a una respuesta de texto libre del
    asistente (responder/asesoria) — "10.000 unidades" se lee como un
    decimal real cuando en realidad es un conteo entero."""

    def test_unidad_siempre_entero_aunque_venga_con_decimales(self):
        self.assertEqual(formatear_cantidad(Decimal("10.000"), Product.Unit.UNIDAD), "10")
        self.assertEqual(formatear_cantidad(Decimal("5.000"), Product.Unit.UNIDAD), "5")

    def test_unidad_redondea_un_decimal_espurio(self):
        # No debería ocurrir en la práctica (current_stock/quantity son
        # conteos), pero si llegara un valor así, nunca hay que mostrar
        # una fracción de "unidad".
        self.assertEqual(formatear_cantidad(Decimal("3.600"), Product.Unit.UNIDAD), "4")

    def test_kg_preserva_decimales_reales(self):
        self.assertEqual(formatear_cantidad(Decimal("2.500"), Product.Unit.KG), "2.5")
        self.assertEqual(formatear_cantidad(Decimal("0.750"), Product.Unit.KG), "0.75")

    def test_kg_recorta_ceros_de_mas_cuando_es_entero(self):
        self.assertEqual(formatear_cantidad(Decimal("10.000"), Product.Unit.KG), "10")

    def test_lt_se_comporta_igual_que_kg(self):
        self.assertEqual(formatear_cantidad(Decimal("1.250"), Product.Unit.LT), "1.25")

    def test_acepta_string_como_entrada(self):
        # productos_mas_vendidos/current_stock a veces llegan como string
        # (ver sales.services.productos_mas_vendidos), no como Decimal.
        self.assertEqual(formatear_cantidad("10.000", Product.Unit.UNIDAD), "10")
        self.assertEqual(formatear_cantidad("2.500", Product.Unit.KG), "2.5")
