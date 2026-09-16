import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { productsApi, salesApi } from '../api/endpoints'
import { extractErrorMessage } from '../api/client'
import { useCompany } from '../context/CompanyContext'
import type { Product, Sale } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { FullScreenSpinner } from '../components/Spinner'
import { formatCLP, formatDateTime } from '../lib/format'

function NewSaleForm({
  companyId,
  products,
  onCreated,
}: {
  companyId: number
  products: Product[]
  onCreated: () => void
}) {
  const [productId, setProductId] = useState<number | ''>('')
  const [quantity, setQuantity] = useState('')
  const [unitPrice, setUnitPrice] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!productId) {
      setError('Elige un producto.')
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      await salesApi.create(companyId, {
        customer_name: customerName || undefined,
        items: [
          {
            product_id: productId,
            quantity,
            unit_price: unitPrice || undefined,
          },
        ],
      })
      setQuantity('')
      setUnitPrice('')
      setCustomerName('')
      onCreated()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="card stack" onSubmit={handleSubmit}>
      <strong>Nueva venta</strong>
      <ErrorBanner message={error} />
      <div className="field">
        <label>Producto</label>
        <select
          required
          value={productId}
          onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}
        >
          <option value="">Elige un producto…</option>
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>Cantidad</label>
        <input
          type="number"
          step="0.001"
          required
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Precio unitario (opcional, usa el de catálogo si se deja vacío)</label>
        <input
          type="number"
          step="0.01"
          value={unitPrice}
          onChange={(e) => setUnitPrice(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Cliente (opcional)</label>
        <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} />
      </div>
      <button className="btn" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Registrando…' : 'Registrar venta'}
      </button>
    </form>
  )
}

export function SalesPage() {
  const { activeCompany } = useCompany()
  const companyId = activeCompany!.id
  const [sales, setSales] = useState<Sale[] | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(() => {
    setError(null)
    salesApi
      .list(companyId)
      .then(setSales)
      .catch((err) => setError(extractErrorMessage(err)))
  }, [companyId])

  useEffect(() => {
    setSales(null)
    load()
    productsApi.list(companyId).then(setProducts).catch(() => undefined)
  }, [companyId, load])

  return (
    <div className="stack">
      <h1>Ventas</h1>
      <ErrorBanner message={error} />

      <button className="btn btn-secondary" type="button" onClick={() => setShowForm((v) => !v)}>
        {showForm ? 'Cerrar' : '+ Nueva venta'}
      </button>

      {showForm && (
        <NewSaleForm
          companyId={companyId}
          products={products}
          onCreated={() => {
            setShowForm(false)
            load()
          }}
        />
      )}

      {sales === null && <FullScreenSpinner label="Cargando ventas…" />}
      {sales?.length === 0 && <p>No hay ventas registradas todavía.</p>}
      {sales?.map((sale) => (
        <div key={sale.id} className="card">
          <strong>
            #{sale.id} — {formatCLP(sale.total)}
          </strong>
          <div style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
            {formatDateTime(sale.sold_at)} · {sale.customer_name || 'Sin cliente'} · {sale.source}
          </div>
        </div>
      ))}
    </div>
  )
}
