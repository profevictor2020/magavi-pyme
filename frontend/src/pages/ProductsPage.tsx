import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { productsApi } from '../api/endpoints'
import { extractErrorMessage } from '../api/client'
import { useCompany } from '../context/CompanyContext'
import type { Product } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { FullScreenSpinner } from '../components/Spinner'
import { formatCLP } from '../lib/format'

function AdjustStockForm({
  product,
  companyId,
  onDone,
}: {
  product: Product
  companyId: number
  onDone: () => void
}) {
  const [cantidad, setCantidad] = useState('')
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await productsApi.adjustStock(companyId, product.id, cantidad, motivo)
      onDone()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="stack" onSubmit={handleSubmit} style={{ marginTop: 'var(--space-2)' }}>
      <ErrorBanner message={error} />
      <div className="field">
        <label>Cantidad (+ entra, - sale)</label>
        <input
          type="number"
          step="0.001"
          required
          value={cantidad}
          onChange={(e) => setCantidad(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Motivo</label>
        <input required value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </div>
      <button className="btn" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Guardando…' : 'Ajustar stock'}
      </button>
    </form>
  )
}

function NewProductForm({ companyId, onCreated }: { companyId: number; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [unit, setUnit] = useState('unidad')
  const [defaultPrice, setDefaultPrice] = useState('')
  const [defaultCost, setDefaultCost] = useState('')
  const [initialStock, setInitialStock] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await productsApi.create(companyId, {
        name,
        unit,
        default_price: defaultPrice || '0',
        default_cost: defaultCost || '0',
        initial_stock: initialStock || undefined,
      })
      setName('')
      setDefaultPrice('')
      setDefaultCost('')
      setInitialStock('')
      onCreated()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="card stack" onSubmit={handleSubmit}>
      <strong>Nuevo producto</strong>
      <ErrorBanner message={error} />
      <div className="field">
        <label>Nombre</label>
        <input required value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="field">
        <label>Unidad</label>
        <input required value={unit} onChange={(e) => setUnit(e.target.value)} />
      </div>
      <div className="field">
        <label>Precio de venta</label>
        <input
          type="number"
          step="0.01"
          value={defaultPrice}
          onChange={(e) => setDefaultPrice(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Costo</label>
        <input
          type="number"
          step="0.01"
          value={defaultCost}
          onChange={(e) => setDefaultCost(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Stock inicial (opcional)</label>
        <input
          type="number"
          step="0.001"
          value={initialStock}
          onChange={(e) => setInitialStock(e.target.value)}
        />
      </div>
      <button className="btn" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Creando…' : 'Crear producto'}
      </button>
    </form>
  )
}

export function ProductsPage() {
  const { activeCompany } = useCompany()
  const companyId = activeCompany!.id
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showLowStock, setShowLowStock] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const load = useCallback(() => {
    setError(null)
    productsApi
      .list(companyId, showLowStock)
      .then(setProducts)
      .catch((err) => setError(extractErrorMessage(err)))
  }, [companyId, showLowStock])

  useEffect(() => {
    setProducts(null)
    load()
  }, [load])

  return (
    <div className="stack">
      <h1>Productos</h1>
      <ErrorBanner message={error} />

      <div className="stack" style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <input
            type="checkbox"
            checked={showLowStock}
            onChange={(e) => setShowLowStock(e.target.checked)}
          />
          Solo stock bajo
        </label>
        <button className="btn btn-secondary" type="button" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cerrar' : '+ Nuevo'}
        </button>
      </div>

      {showForm && (
        <NewProductForm
          companyId={companyId}
          onCreated={() => {
            setShowForm(false)
            load()
          }}
        />
      )}

      {products === null && <FullScreenSpinner label="Cargando productos…" />}
      {products?.length === 0 && <p>No hay productos todavía.</p>}
      {products?.map((product) => (
        <div key={product.id} className="card">
          <strong>{product.name}</strong>
          <div style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
            Stock: {product.current_stock} {product.unit} · Venta: {formatCLP(product.default_price)}
          </div>
          <button
            className="btn btn-secondary"
            type="button"
            style={{ marginTop: 'var(--space-2)' }}
            onClick={() => setExpandedId((current) => (current === product.id ? null : product.id))}
          >
            {expandedId === product.id ? 'Ocultar' : 'Ajustar stock'}
          </button>
          {expandedId === product.id && (
            <AdjustStockForm
              product={product}
              companyId={companyId}
              onDone={() => {
                setExpandedId(null)
                load()
              }}
            />
          )}
        </div>
      ))}
    </div>
  )
}
