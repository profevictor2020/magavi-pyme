import { expenseCategoryLabel, formatCLP, formatDateTime, formatQuantity, periodLabel } from '../lib/format'
import {
  isExpense,
  isExpenseList,
  isLowStockList,
  isMovement,
  isPeriodSummary,
  isProduct,
  isProductList,
  isProductSalesSummary,
  isReceipt,
  isReceiptList,
  isSalesPeriodTotal,
  isTopSellingList,
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

  if (isProductSalesSummary(result)) {
    // Se revisa antes que isPeriodSummary: comparten today/week, pero
    // esta forma está acotada a un producto (product_id) y cuenta
    // unidades, no número de ventas.
    return (
      <div className="result-card">
        <strong>{result.product_name}</strong>
        <div>
          Hoy: {formatQuantity(result.today.quantity)} vendidas ({formatCLP(result.today.total)})
        </div>
        <div>
          Esta semana: {formatQuantity(result.week.quantity)} vendidas (
          {formatCLP(result.week.total)})
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

  if (isSalesPeriodTotal(result)) {
    return (
      <div className="result-card">
        <strong>{periodLabel(result.period, result.date_from, result.date_to)}</strong>
        <div>
          {formatCLP(result.total)} ({result.count} ventas)
        </div>
      </div>
    )
  }

  if (isProduct(result)) {
    // Misma forma para crear_producto y actualizar_producto — el texto
    // no dice "creado" ni "actualizado" porque no sabe cuál de los dos
    // intents lo generó, solo el estado final del producto.
    return (
      <div className="result-card">
        <strong>
          {result.name} — {formatCLP(result.default_price)}
        </strong>
        <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
          Stock: {formatQuantity(result.current_stock)} {result.unit}
        </div>
        {result.low_stock_threshold !== undefined && Number(result.low_stock_threshold) > 0 && (
          <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
            Aviso de stock bajo desde: {formatQuantity(result.low_stock_threshold)} {result.unit}
          </div>
        )}
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

  if (isTopSellingList(result)) {
    if (result.length === 0) return <div className="result-card">Todavía no hay ventas registradas.</div>
    return (
      <ol className="result-items result-card">
        {result.map((product) => (
          <li key={product.product_id}>
            {product.product_name}: {formatQuantity(product.quantity)} vendidas —{' '}
            {formatCLP(product.total)}
          </li>
        ))}
      </ol>
    )
  }

  if (isExpense(result)) {
    return (
      <div className="result-card">
        <strong>
          Gasto: {expenseCategoryLabel(result.category)} — {formatCLP(result.amount)}
        </strong>
        {result.description && (
          <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
            {result.description}
          </div>
        )}
      </div>
    )
  }

  if (isExpenseList(result)) {
    if (result.length === 0) return <div className="result-card">Sin gastos registrados.</div>
    return (
      <ul className="result-items result-card">
        {result.map((expense) => (
          <li key={expense.id}>
            {expenseCategoryLabel(expense.category)}
            {expense.description && ` — ${expense.description}`}: {formatCLP(expense.amount)}{' '}
            <span style={{ color: 'var(--color-muted)' }}>
              ({formatDateTime(expense.created_at)})
            </span>
          </li>
        ))}
      </ul>
    )
  }

  if (isReceiptList(result)) {
    // Se revisa al final, después de las demás formas en lista: un
    // array vacío es ambiguo entre todas ellas (ver isProductList
    // arriba en resultShapes.ts), así que el orden decide qué mensaje
    // gana — se prioriza mantener el de las formas ya existentes.
    if (result.length === 0) return <div className="result-card">Sin ventas registradas.</div>
    return (
      <div className="result-items result-card">
        {result.map((venta) => (
          <div key={venta.id} style={{ marginBottom: '0.5rem' }}>
            <strong>
              Venta #{venta.id} — {formatCLP(venta.total)}
            </strong>
            <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
              {venta.sold_at && formatDateTime(venta.sold_at)} ·{' '}
              {venta.customer_name || 'Sin nombre registrado'}
            </div>
            <ul className="result-items">
              {venta.items.map((item) => (
                <li key={item.id}>
                  Producto #{item.product} · {formatQuantity(item.quantity)} ×{' '}
                  {formatCLP(item.unit_price)} = {formatCLP(item.subtotal)}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    )
  }

  return <pre className="result-card result-json">{JSON.stringify(result, null, 2)}</pre>
}
