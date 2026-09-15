# MAGAVI — Visión de Producto

## 1. Problema

Los dueños de micro y pequeñas empresas chilenas (almacenes, ferreterías,
cafeterías, talleres, etc.) operan la mayor parte del día **lejos de un
computador**: atendiendo, vendiendo, recibiendo mercadería. El software de
gestión tradicional (ERP/planillas) asume que alguien se sienta a
"administrar" el negocio. En la práctica, nadie tiene ese tiempo.

## 2. Propuesta de valor

> "El emprendedor no debería tener que aprender a usar un software complejo.
> Debería poder decirle al sistema qué necesita hacer."

MAGAVI no es "otro ERP". Es un **asistente conversacional** que administra el
negocio en background. La interacción principal es lenguaje natural (texto o
foto), no formularios. Las pantallas tradicionales existen como respaldo,
pero no son el centro de la experiencia.

Diferenciadores:

- **Mobile-first real**: diseñado para pulgar y una mano, no un ERP de
  escritorio "adaptado" a pantalla chica.
- **Conversación como UI principal**: registrar una venta es una frase, no un
  formulario de 8 campos.
- **Captura por foto**: una boleta/factura se transforma en datos
  estructurados, con confirmación humana antes de guardar.
- **Privacidad por diseño**: el motor de IA corre en infraestructura propia
  de MAGAVI, no se envían datos de negocio a terceros por defecto.

## 3. Usuario objetivo (persona)

**"Doña Marcela"**, 45 años, dueña de un almacén/cafetería. Usa WhatsApp a
diario, no usa Excel con fluidez, tiene el celular en la mano todo el día.
Quiere saber "cómo va el día" sin sacar cuentas a mano, y registrar ventas
y compras sin perder tiempo de atención al cliente.

Usuario secundario: un/a ayudante o socio/a que también registra
movimientos desde su propio celular, para la misma empresa.

## 4. Alcance del MVP

Incluye (ver `ARCHITECTURE.md` y `DATA_MODEL.md` para el detalle técnico):

1. Autenticación de usuarios.
2. Empresas (multi-tenant).
3. Usuarios asociados a empresas (roles básicos).
4. Asistente conversacional (texto; voz es UI futura, no bloqueante).
5. Productos.
6. Ventas.
7. Compras.
8. Inventario (derivado de ventas/compras + ajustes manuales).
9. Caja / movimientos de efectivo.
10. Captura y procesamiento de documentos por foto (OCR + extracción).
11. Dashboard/resumen simple (hoy, semana).
12. Arquitectura modular multiempresa.

## 5. Explícitamente fuera de alcance del MVP

- RRHH y remuneraciones.
- Contabilidad completa (libros, F29, etc.).
- Facturación electrónica SII (emisión de DTE).
- CRM avanzado (segmentación, campañas).
- Agenda / calendario.
- Marketplace / venta entre empresas.
- Multi-idioma (solo español).
- Múltiples métodos de pago/conciliación bancaria.
- Roles y permisos granulares más allá de owner/admin/staff.

Cualquier feature no listada en la sección 4 se considera scope creep y debe
rechazarse o diferirse explícitamente a una fase posterior documentada.

## 6. Guion de demostración del MVP (criterio de éxito funcional)

Ver `ROADMAP.md` Fase 12. Resumen: desde un celular, con sesión iniciada,
el usuario pregunta "¿cuánto vendí hoy?", registra una venta por
conversación con confirmación explícita, ve el inventario/caja
actualizados, y luego fotografía un documento de compra que también queda
registrado tras confirmación — todo aislado a los datos de su empresa.

## 7. Métricas de éxito propuestas (para validar el MVP, no vanity metrics)

- % de registros (venta/compra) completados vía asistente vs. formulario
  manual.
- Tiempo promedio desde "abrir la app" hasta "venta registrada" por
  conversación.
- Tasa de confirmación vs. corrección en extracción de documentos
  (mide calidad del OCR/estructuración).
- Cero incidentes de fuga de datos entre empresas (métrica de seguridad,
  no de producto, pero es un gate de release).

## 8. Riesgos de producto

- Que el usuario no confíe en "hablarle" al sistema para operaciones con
  dinero → mitigado con confirmación explícita siempre visible.
- Que la extracción de documentos falle seguido con boletas chilenas reales
  (mala calidad de foto, papel térmico desgastado) → mitigado con revisión
  editable obligatoria, nunca autoregistro.
- Ambigüedad en lenguaje natural ("vendí unos cafés") → el asistente debe
  pedir aclaración, nunca asumir cantidades/precios faltantes.
