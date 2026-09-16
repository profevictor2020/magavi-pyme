"""Smoke test manual contra un LLMProvider real (ver docs/DECISIONS.md
ADR-010 y docs/ROADMAP.md Fase 8).

Pensado para correr en un job de CI activado a mano
(`workflow_dispatch`, ver .github/workflows/llm-check.yml), nunca en el
pipeline normal de cada push: hace una llamada de red real a un
proveedor de LLM y no debe bloquear ni ralentizar el flujo rápido de
cada commit.
"""

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from assistant.orchestrator import interpretar_y_proponer
from catalog.models import Product
from companies.models import Company, CompanyUser

MENSAJE_DE_PRUEBA = "Vendí 3 cafés a 2500 pesos cada uno"


class Command(BaseCommand):
    help = "Prueba el Orchestrator del asistente contra el LLMProvider real configurado."

    def handle(self, *args, **options):
        company = Company.objects.create(name="Smoke Test Co", rut="smoke-test-rut")
        user = User.objects.create_user(email="smoke-test@example.cl", password="x")
        CompanyUser.objects.create(company=company, user=user, role=CompanyUser.Role.OWNER)
        Product.objects.create(
            company=company, name="Café", default_price="2500.00", current_stock="20"
        )

        self.stdout.write(f"Mensaje enviado al LLM: {MENSAJE_DE_PRUEBA!r}")

        resultado = interpretar_y_proponer(company=company, user=user, mensaje=MENSAJE_DE_PRUEBA)

        self.stdout.write(f"Resultado del Orchestrator: {resultado}")

        if resultado.get("status") != "pending_confirmation":
            raise CommandError(
                f"Se esperaba 'pending_confirmation'; el LLM real devolvió: {resultado}"
            )
        if resultado.get("intent") != "crear_venta":
            raise CommandError(
                f"Se esperaba intent 'crear_venta'; se obtuvo: {resultado.get('intent')!r}"
            )

        self.stdout.write(
            self.style.SUCCESS("OK: el LLM real interpretó correctamente el mensaje de prueba.")
        )
