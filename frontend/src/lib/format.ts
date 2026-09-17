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
  consultar_ventas: 'Consultar ventas',
  consultar_stock_bajo: 'Consultar stock bajo',
  consultar_stock_producto: 'Consultar stock de un producto',
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
}

export function paramLabel(key: string): string {
  return PARAM_LABELS[key] ?? key
}
