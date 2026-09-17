// Formas conocidas del resultado de un intent (ejecutado o confirmado) y
// sus type guards. Compartido entre ResultView (render visual) y
// speech.ts (resumen hablado) para no duplicar la lógica de detección.

export interface ReceiptLike {
  id: number
  total: string
  status: string
  items: {
    id: number
    product: number
    quantity: string
    unit_price?: string
    unit_cost?: string
    subtotal: string
  }[]
  customer_name?: string
  supplier_name?: string
  sold_at?: string
  purchased_at?: string
}

export interface MovementLike {
  id: number
  product: number
  type: string
  quantity: string
  balance_after: string
  reason: string
}

export interface PeriodSummaryLike {
  today: { total: string; count: number }
  week: { total: string; count: number }
}

export interface LowStockLike {
  id: number
  name: string
  current_stock: string
  low_stock_threshold: string
}

export interface ProductLike {
  id: number
  name: string
  unit: string
  default_price: string
  current_stock: string
}

export function isReceipt(value: unknown): value is ReceiptLike {
  return (
    !!value &&
    typeof value === 'object' &&
    Array.isArray((value as ReceiptLike).items) &&
    'total' in value
  )
}

export function isMovement(value: unknown): value is MovementLike {
  return !!value && typeof value === 'object' && 'balance_after' in value
}

export function isPeriodSummary(value: unknown): value is PeriodSummaryLike {
  return !!value && typeof value === 'object' && 'today' in value && 'week' in value
}

export function isLowStockList(value: unknown): value is LowStockLike[] {
  // "low_stock_threshold" (no solo "current_stock") es lo que distingue
  // esta forma de isProductList — ambas son arrays de objetos con stock.
  return Array.isArray(value) && (value.length === 0 || 'low_stock_threshold' in value[0])
}

export function isProduct(value: unknown): value is ProductLike {
  return !!value && typeof value === 'object' && 'default_price' in value && 'unit' in value
}

export function isProductList(value: unknown): value is ProductLike[] {
  return Array.isArray(value) && (value.length === 0 || 'default_price' in value[0])
}
