import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { productsApi, purchasesApi } from '../api/endpoints'
import { extractErrorMessage } from '../api/client'
import { useCompany } from '../context/CompanyContext'
import type { Product, Purchase } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { FullScreenSpinner } from '../components/Spinner'
import { formatCLP, formatDateTime } from '../lib/format'

function NewPurchaseForm({
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
  const [unitCost, setUnitCost] = useState('')
  const [supplierName, setSupplierName] = useState('')
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
      await purchasesApi.create(companyId, {
        supplier_name: supplierName || undefined,
        items: [
          {
            product_id: productId,
            quantity,
            unit_cost: unitCost || undefined,
          },
        ],
      })
      setQuantity('')
      setUnitCost('')
      setSupplierName('')
      onCreated()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="card stack" onSubmit={handleSubmit}>
      <strong>Nueva compra</strong>
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
        <label>Costo unitario (opcional, usa el de catálogo si se deja vacío)</label>
        <input
          type="number"
          step="0.01"
          value={unitCost}
          onChange={(e) => setUnitCost(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Proveedor (opcional)</label>
        <input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} />
      </div>
      <button className="btn" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Registrando…' : 'Registrar compra'}
      </button>
    </form>
  )
}

export function PurchasesPage() {
  const { activeCompany } = useCompany()
  const companyId = activeCompany!.id
  const [purchases, setPurchases] = useState<Purchase[] | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(() => {
    setError(null)
    purchasesApi
      .list(companyId)
      .then(setPurchases)
      .catch((err) => setError(extractErrorMessage(err)))
  }, [companyId])

  useEffect(() => {
    setPurchases(null)
    load()
    productsApi.list(companyId).then(setProducts).catch(() => undefined)
  }, [companyId, load])

  return (
    <div className="stack">
      <h1>Compras</h1>
      <ErrorBanner message={error} />

      <button className="btn btn-secondary" type="button" onClick={() => setShowForm((v) => !v)}>
        {showForm ? 'Cerrar' : '+ Nueva compra'}
      </button>

      {showForm && (
        <NewPurchaseForm
          companyId={companyId}
          products={products}
          onCreated={() => {
            setShowForm(false)
            load()
          }}
        />
      )}

      {purchases === null && <FullScreenSpinner label="Cargando compras…" />}
      {purchases?.length === 0 && <p>No hay compras registradas todavía.</p>}
      {purchases?.map((purchase) => (
        <div key={purchase.id} className="card">
          <strong>
            #{purchase.id} — {formatCLP(purchase.total)}
          </strong>
          <div style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
            {formatDateTime(purchase.purchased_at)} · {purchase.supplier_name || 'Sin proveedor'} ·{' '}
            {purchase.source}
          </div>
        </div>
      ))}
    </div>
  )
}
