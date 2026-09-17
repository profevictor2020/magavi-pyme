export function formatCLP(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined) return '—'
  const value = typeof amount === 'string' ? Number(amount) : amount
  if (Number.isNaN(value)) return String(amount)
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    maximumFractionDigits: 0,
  }).format(value)
}

/** Para leer un monto en voz alta (ver lib/speech.ts): el "$" de
 * formatCLP es la convención correcta para mostrar en pantalla, pero al
 * hablarlo un sintetizador de voz puede leerlo como "dólares" en vez de
 * pesos chilenos (el símbolo "$" no es exclusivo de CLP). Dice "pesos"
 * explícito para que no quede ambiguo.
 *
 * Sin separador de miles: formatCLP usa "." para eso ("7.000"), que es
 * la convención correcta en pantalla, pero un sintetizador de voz suele
 * leer ese "." como punto decimal — "7.000" se escucha como "7", no
 * como "siete mil". Un entero plano ("7000") no tiene esa ambigüedad. */
export function formatCLPSpoken(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined) return ''
  const value = typeof amount === 'string' ? Number(amount) : amount
  if (Number.isNaN(value)) return String(amount)
  return `${Math.round(value)} pesos`
}

/** El backend guarda cantidades/stock como decimal con 3 dígitos
 * (soporta kg/lt fraccionarios), pero mostrar "10.000" para algo en
 * unidades es confuso. Recorta los ceros que sobran sin perder un
 * decimal real (2.500 -> "2.5", 10.000 -> "10"). */
export function formatQuantity(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const num = typeof value === 'string' ? Number(value) : value
  if (Number.isNaN(num)) return String(value)
  return num.toString()
}

export function formatDateTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat('es-CL', { dateStyle: 'short', timeStyle: 'short' }).format(
      new Date(iso),
    )
  } catch {
    return iso
  }
}

const INTENT_LABELS: Record<string, string> = {
  crear_venta: 'Registrar venta',
  registrar_compra: 'Registrar compra',
  ajustar_inventario: 'Ajustar inventario',
  crear_producto: 'Crear producto',
  actualizar_producto: 'Actualizar producto',
  registrar_gasto: 'Registrar gasto',
  actualizar_gasto: 'Corregir gasto',
  consultar_gastos: 'Consultar gastos',
  consultar_ventas: 'Consultar ventas',
  consultar_ventas_producto: 'Consultar ventas de un producto',
  consultar_productos_mas_vendidos: 'Consultar productos más vendidos',
  consultar_stock_bajo: 'Consultar stock bajo',
  consultar_producto: 'Consultar un producto',
  consultar_catalogo: 'Consultar catálogo',
}

export function intentLabel(name: string): string {
  return INTENT_LABELS[name] ?? name
}

const PARAM_LABELS: Record<string, string> = {
  product_id: 'Producto (ID)',
  quantity: 'Cantidad',
  unit_price: 'Precio unitario',
  unit_cost: 'Costo unitario',
  customer_name: 'Cliente',
  supplier_name: 'Proveedor',
  cantidad: 'Cantidad',
  motivo: 'Motivo',
  name: 'Nombre',
  unit: 'Unidad',
  default_price: 'Precio de venta',
  default_cost: 'Costo',
  initial_stock: 'Stock inicial',
  low_stock_threshold: 'Mínimo de stock',
  amount: 'Monto',
  category: 'Categoría',
  description: 'Descripción',
  cash_movement_id: 'Gasto (ID)',
}

export function paramLabel(key: string): string {
  return PARAM_LABELS[key] ?? key
}

const EXPENSE_CATEGORY_LABELS: Record<string, string> = {
  arriendo: 'Arriendo',
  sueldos: 'Sueldos',
  servicios: 'Servicios',
  otro: 'Otro',
}

export function expenseCategoryLabel(category: string | null | undefined): string {
  if (!category) return '—'
  return EXPENSE_CATEGORY_LABELS[category] ?? category
}
