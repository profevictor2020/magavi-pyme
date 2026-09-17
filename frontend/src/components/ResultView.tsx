import { formatCLP, formatQuantity } from '../lib/format'
import {
  isLowStockList,
  isMovement,
  isPeriodSummary,
  isProduct,
  isProductList,
  isReceipt,
} from '../lib/resultShapes'

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
              Producto #{item.product} · {formatQuantity(item.quantity)} ×{' '}
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
          {formatQuantity(Math.abs(Number(result.quantity)))} ({result.reason})
        </div>
        <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
          Nuevo stock: {formatQuantity(result.balance_after)}
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

  if (isProduct(result)) {
    return (
      <div className="result-card">
        <strong>
          Producto creado: {result.name} ({formatCLP(result.default_price)})
        </strong>
        <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
          Stock: {formatQuantity(result.current_stock)} {result.unit}
        </div>
      </div>
    )
  }

  if (isProductList(result)) {
    if (result.length === 0) return <div className="result-card">Sin productos en el catálogo.</div>
    return (
      <ul className="result-items result-card">
        {result.map((product) => (
          <li key={product.id}>
            {product.name}: {formatQuantity(product.current_stock)} {product.unit} —{' '}
            {formatCLP(product.default_price)}
          </li>
        ))}
      </ul>
    )
  }

  if (isLowStockList(result)) {
    if (result.length === 0) return <div className="result-card">Sin productos con stock bajo.</div>
    return (
      <ul className="result-items result-card">
        {result.map((product) => (
          <li key={product.id}>
            {product.name}: {formatQuantity(product.current_stock)} (mínimo{' '}
            {formatQuantity(product.low_stock_threshold)})
          </li>
        ))}
      </ul>
    )
  }

  return <pre className="result-card result-json">{JSON.stringify(result, null, 2)}</pre>
}
