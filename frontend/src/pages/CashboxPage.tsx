import { useEffect, useState } from 'react'
import { cashboxApi } from '../api/endpoints'
import { extractErrorMessage } from '../api/client'
import { useCompany } from '../context/CompanyContext'
import type { CashboxSummary } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { FullScreenSpinner } from '../components/Spinner'
import { formatCLP, formatQuantity } from '../lib/format'

export function CashboxPage() {
  const { activeCompany } = useCompany()
  const companyId = activeCompany!.id
  const [summary, setSummary] = useState<CashboxSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setSummary(null)
    setError(null)
    cashboxApi
      .summary(companyId)
      .then(setSummary)
      .catch((err) => setError(extractErrorMessage(err)))
  }, [companyId])

  if (error) return <ErrorBanner message={error} />
  if (!summary) return <FullScreenSpinner label="Cargando resumen…" />

  return (
    <div className="stack">
      <h1>Cómo va el negocio</h1>

      <section className="card">
        <strong>Caja — hoy</strong>
        <div>Ingresos: {formatCLP(summary.cash.today.income)}</div>
        <div>Egresos: {formatCLP(summary.cash.today.expense)}</div>
        <div>
          <strong>Balance: {formatCLP(summary.cash.today.balance)}</strong>
        </div>
      </section>

      <section className="card">
        <strong>Caja — esta semana</strong>
        <div>Ingresos: {formatCLP(summary.cash.week.income)}</div>
        <div>Egresos: {formatCLP(summary.cash.week.expense)}</div>
        <div>
          <strong>Balance: {formatCLP(summary.cash.week.balance)}</strong>
        </div>
      </section>

      <section className="card">
        <strong>Ventas</strong>
        <div>
          Hoy: {formatCLP(summary.sales.today.total)} ({summary.sales.today.count})
        </div>
        <div>
          Semana: {formatCLP(summary.sales.week.total)} ({summary.sales.week.count})
        </div>
      </section>

      <section className="card">
        <strong>Stock bajo</strong>
        {summary.low_stock_products.length === 0 ? (
          <p style={{ color: 'var(--color-muted)' }}>Ningún producto con stock bajo. 🎉</p>
        ) : (
          <ul className="result-items">
            {summary.low_stock_products.map((product) => (
              <li key={product.id}>
                {product.name}: {formatQuantity(product.current_stock)} (mínimo{' '}
                {formatQuantity(product.low_stock_threshold)})
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
