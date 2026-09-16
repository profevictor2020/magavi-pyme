import { formatCLP } from '../lib/format'

interface ReceiptLike {
  id: number
  total: string
  status: string
  items: { id: number; product: number; quantity: string; unit_price?: string; unit_cost?: string; subtotal: string }[]
  customer_name?: string
  supplier_name?: string
  sold_at?: string
  purchased_at?: string
}

interface MovementLike {
  id: number
  product: number
  type: string
  quantity: string
  balance_after: string
  reason: string
}

interface PeriodSummaryLike {
  today: { total: string; count: number }
  week: { total: string; count: number }
}

interface LowStockLike {
  id: number
  name: string
  current_stock: string
  low_stock_threshold: string
}

function isReceipt(value: unknown): value is ReceiptLike {
  return (
    !!value &&
    typeof value === 'object' &&
    Array.isArray((value as ReceiptLike).items) &&
    'total' in value
  )
}

function isMovement(value: unknown): value is MovementLike {
  return !!value && typeof value === 'object' && 'balance_after' in value
}

function isPeriodSummary(value: unknown): value is PeriodSummaryLike {
  return !!value && typeof value === 'object' && 'today' in value && 'week' in value
}

function isLowStockList(value: unknown): value is LowStockLike[] {
  return Array.isArray(value) && (value.length === 0 || 'current_stock' in value[0])
}

/** Renderiza el resultado de un intent ejecutado/confirmado. Cubre las
 * formas conocidas (venta/compra, ajuste de inventario, resúmenes de
 * solo lectura); cualquier otra forma cae a un volcado JSON legible en
 * vez de fallar silenciosamente. */
export function ResultView({ result }: { result: unknown }) {
  if (isReceipt(result)) {
    const isSale = 'sold_at' in result
    return (
      <div className="result-card">
        <strong>
          {isSale ? 'Venta' : 'Compra'} #{result.id} — {formatCLP(result.total)}
        </strong>
        <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
          {result.customer_name || result.supplier_name || 'Sin nombre registrado'}
        </div>
        <ul className="result-items">
          {result.items.map((item) => (
            <li key={item.id}>
              Producto #{item.product} · {item.quantity} ×{' '}
              {formatCLP(item.unit_price ?? item.unit_cost)} = {formatCLP(item.subtotal)}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  if (isMovement(result)) {
    return (
      <div className="result-card">
        <strong>Movimiento de inventario</strong>
        <div>
          Producto #{result.product}: {result.type === 'in' ? '+' : '-'}
          {result.quantity} ({result.reason})
        </div>
        <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
          Nuevo stock: {result.balance_after}
        </div>
      </div>
    )
  }

  if (isPeriodSummary(result)) {
    return (
      <div className="result-card">
        <div>
          Hoy: {formatCLP(result.today.total)} ({result.today.count} ventas)
        </div>
        <div>
          Esta semana: {formatCLP(result.week.total)} ({result.week.count} ventas)
        </div>
      </div>
    )
  }

  if (isLowStockList(result)) {
    if (result.length === 0) return <div className="result-card">Sin productos con stock bajo.</div>
    return (
      <ul className="result-items result-card">
        {result.map((product) => (
          <li key={product.id}>
            {product.name}: {product.current_stock} (mínimo {product.low_stock_threshold})
          </li>
        ))}
      </ul>
    )
  }

  return <pre className="result-card result-json">{JSON.stringify(result, null, 2)}</pre>
}
