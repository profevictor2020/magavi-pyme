# MAGAVI — Estrategia de Testing

## 1. Principio general

Una fase no está terminada porque compile. Debe demostrarse con pruebas
automáticas **y** una prueba manual documentada, según el criterio de
aceptación definido en `ROADMAP.md` para esa fase.

## 2. Pirámide de pruebas

```
        E2E (Playwright, viewport móvil)
       /----------------------------------\
      /  Pruebas de seguridad / aislamiento \
     /----------------------------------------\
    /       Integration (API, DB real)          \
   /------------------------------------------------\
  /            Unit (Tool Layer, cálculos)            \
 /--------------------------------------------------------\
```

- **Unit**: funciones del Tool Layer, cálculos (totales, stock, caja),
  validación de `IntentSchema`. Sin HTTP, sin base de datos real cuando sea
  posible (o con transacción de test rápida).
- **Integration**: endpoints DRF con `APIClient`, base de datos de test
  real, verificando request→respuesta→efectos en BD.
- **Aislamiento multiempresa**: batería dedicada y obligatoria desde Fase
  2. Patrón fijo: crear Empresa A y Empresa B con datos equivalentes,
  autenticar como usuario de A, verificar que ningún listado ni acceso
  directo por `id` expone datos de B (incluyendo el caso IDOR: acceder a
  un `id` válido pero de otra empresa debe responder 404, no 403, para no
  confirmar existencia).
- **Seguridad**: casos de autenticación/autorización rota, prompt
  injection sobre el asistente, subida de archivos inválidos, intentos de
  bypass de confirmación.
- **E2E**: Playwright en viewport móvil, reservado para el guion de demo
  completo (Fase 12) y flujos críticos de Fase 10 en adelante. No se usa
  para cubrir lógica de negocio (eso ya está en unit/integration).

## 3. Herramientas propuestas

- Backend: `pytest` + `pytest-django`, `factory_boy` para fixtures/datos
  de prueba, `pytest-cov` para cobertura.
- Frontend: `vitest`/`@testing-library/react` para componentes clave.
- E2E: Playwright (ya disponible en el entorno de desarrollo).
- CI: GitHub Actions ejecuta lint + unit + integration en cada PR desde
  Fase 1; E2E se incorpora al pipeline desde Fase 10/12 (más lento, no
  bloquea cada commit necesariamente pero sí bloquea la fase).

## 4. Datos de prueba

- `factory_boy` factories por entidad, siempre con `company` explícito (
  nunca un default global) para forzar que cada test declare a qué empresa
  pertenecen sus datos — esto hace los tests de aislamiento naturales de
  escribir y difíciles de "hacer trampa".
- Nunca usar datos reales de clientes/proveedores en fixtures o tests.

## 5. Gate obligatorio por fase (Definition of Done)

Ninguna fase se marca como completa sin:

1. Objetivo cumplido según `ROADMAP.md`.
2. Tests automáticos nuevos en verde (unit + integration correspondientes,
   y aislamiento si la fase agrega un modelo/endpoint de negocio).
3. Prueba manual ejecutada y su resultado documentado (puede ser un
   párrafo en el PR o commit, no requiere ceremonia).
4. Criterios de aceptación de esa fase cumplidos explícitamente, uno por
   uno.
5. Sin regresiones: la suite completa de fases anteriores sigue en verde.
6. Confirmación explícita del usuario/product owner antes de iniciar la
   fase siguiente.

## 6. Qué NO se hace en el MVP

- No se persigue 100% de cobertura de línea; se prioriza cobertura de
  reglas de negocio y de los puntos de riesgo listados en `SECURITY.md`.
- No se automatiza pentesting externo (queda como recomendación
  post-MVP).
- No se testea rendimiento/carga de forma formal en el MVP (se puede
  anotar como deuda técnica si el LLM/OCR resultan lentos en la práctica).
