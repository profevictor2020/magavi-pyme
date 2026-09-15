"""Registro de intents soportados y adaptador hacia el Tool Layer.

Este módulo es, junto con assistant/services.py, la "capa de
herramientas" de la Fase 7 (ver docs/ROADMAP.md y
docs/ARCHITECTURE.md #3.4): traduce un intent ya validado —construido a
mano en esta fase, por un LLM desde la Fase 8— en una llamada al Tool
Layer real, el mismo que usan los endpoints tradicionales. El asistente
nunca ejecuta lógica de negocio propia; solo resuelve nombres/ids a
objetos concretos y delega.
"""

from dataclasses import dataclass
from typing import Callable

from catalog.services import consultar_stock_bajo, get_product_or_raise
from inventory.services import ajustar_inventario
from purchases.serializers import PurchaseCreateSerializer
from purchases.services import registrar_compra
from sales.serializers import SaleCreateSerializer
from sales.services import consultar_ventas, crear_venta

from .serializers import AjustarInventarioIntentSerializer, EmptyParamsSerializer


def _resolve_items(company, raw_items, price_field):
    resolved = []
    for raw_item in raw_items:
        product = get_product_or_raise(company=company, product_id=raw_item["product_id"])
        item = {"product": product, "quantity": raw_item["quantity"]}
        if price_field in raw_item:
            item[price_field] = raw_item[price_field]
        resolved.append(item)
    return resolved


def _ejecutar_crear_venta(*, company, user, params):
    items = _resolve_items(company, params["items"], "unit_price")
    return crear_venta(
        company=company,
        user=user,
        items=items,
        customer_name=params.get("customer_name", ""),
        origen="assistant",
    )


def _ejecutar_registrar_compra(*, company, user, params):
    items = _resolve_items(company, params["items"], "unit_cost")
    return registrar_compra(
        company=company,
        user=user,
        items=items,
        supplier_name=params.get("supplier_name", ""),
        origen="assistant",
    )


def _ejecutar_ajustar_inventario(*, company, user, params):
    product = get_product_or_raise(company=company, product_id=params["product_id"])
    return ajustar_inventario(
        company=company,
        user=user,
        product=product,
        cantidad=params["cantidad"],
        motivo=params["motivo"],
        origen="manual",
    )


def _ejecutar_consultar_ventas(*, company, user, params):
    return consultar_ventas(company=company)


def _ejecutar_consultar_stock_bajo(*, company, user, params):
    return consultar_stock_bajo(company=company)


@dataclass(frozen=True)
class IntentDefinition:
    parameter_serializer: type
    requires_confirmation: bool
    executor: Callable


INTENTS: dict[str, IntentDefinition] = {
    "crear_venta": IntentDefinition(SaleCreateSerializer, True, _ejecutar_crear_venta),
    "registrar_compra": IntentDefinition(
        PurchaseCreateSerializer, True, _ejecutar_registrar_compra
    ),
    "ajustar_inventario": IntentDefinition(
        AjustarInventarioIntentSerializer, True, _ejecutar_ajustar_inventario
    ),
    "consultar_ventas": IntentDefinition(EmptyParamsSerializer, False, _ejecutar_consultar_ventas),
    "consultar_stock_bajo": IntentDefinition(
        EmptyParamsSerializer, False, _ejecutar_consultar_stock_bajo
    ),
}


def ejecutar_intent(*, company, user, intent_name, validated_params):
    definition = INTENTS[intent_name]
    return definition.executor(company=company, user=user, params=validated_params)
