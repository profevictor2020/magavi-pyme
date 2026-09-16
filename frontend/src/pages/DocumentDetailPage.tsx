import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { documentsApi, productsApi } from '../api/endpoints'
import { extractErrorMessage } from '../api/client'
import { useCompany } from '../context/CompanyContext'
import type { MagaviDocument, Product } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { FullScreenSpinner } from '../components/Spinner'
import { ResultView } from '../components/ResultView'
import type { Purchase, Sale } from '../api/types'

const POLL_STATUSES = new Set(['uploaded', 'processing'])
const POLL_INTERVAL_MS = 1500

interface ItemDraft {
  productId: number | ''
  quantity: string
  unitAmount: string
}

function ConfirmForm({
  companyId,
  doc,
  products,
  onDone,
}: {
  companyId: number
  doc: MagaviDocument
  products: Product[]
  onDone: (result: Sale | Purchase) => void
}) {
  const structured = doc.extraction?.structured_data
  const [documentType, setDocumentType] = useState<'purchase' | 'sale'>(
    structured?.document_type === 'sale' ? 'sale' : 'purchase',
  )
  const [partyName, setPartyName] = useState(structured?.counterparty_name ?? '')
  const [items, setItems] = useState<ItemDraft[]>(() => {
    const draftItems = structured?.items ?? []
    if (draftItems.length === 0) return [{ productId: '', quantity: '', unitAmount: '' }]
    return draftItems.map((item) => ({
      productId: item.product_id ?? '',
      quantity: item.quantity ?? '',
      unitAmount: item.unit_price ?? '',
    }))
  })
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const updateItem = (index: number, patch: Partial<ItemDraft>) => {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (items.some((item) => !item.productId)) {
      setError('Elige el producto correspondiente para cada ítem.')
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      const response = await documentsApi.confirm(companyId, doc.id, {
        document_type: documentType,
        party_name: partyName || undefined,
        items: items.map((item) => ({
          product_id: item.productId as number,
          quantity: item.quantity,
          unit_amount: item.unitAmount || undefined,
        })),
      })
      onDone(response.result as Sale | Purchase)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="card stack" onSubmit={handleSubmit}>
      <strong>Revisa y confirma</strong>
      <ErrorBanner message={error} />
      <div className="field">
        <label>Tipo de documento</label>
        <select value={documentType} onChange={(e) => setDocumentType(e.target.value as 'purchase' | 'sale')}>
          <option value="purchase">Compra</option>
          <option value="sale">Venta</option>
        </select>
      </div>
      <div className="field">
        <label>{documentType === 'purchase' ? 'Proveedor' : 'Cliente'}</label>
        <input value={partyName} onChange={(e) => setPartyName(e.target.value)} />
      </div>

      {items.map((item, index) => (
        <div key={index} className="stack" style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 'var(--space-3)' }}>
          <div className="field">
            <label>Producto</label>
            <select
              required
              value={item.productId}
              onChange={(e) =>
                updateItem(index, { productId: e.target.value ? Number(e.target.value) : '' })
              }
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
              value={item.quantity}
              onChange={(e) => updateItem(index, { quantity: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Precio/costo unitario (opcional)</label>
            <input
              type="number"
              step="0.01"
              value={item.unitAmount}
              onChange={(e) => updateItem(index, { unitAmount: e.target.value })}
            />
          </div>
          {items.length > 1 && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setItems((prev) => prev.filter((_, i) => i !== index))}
            >
              Quitar ítem
            </button>
          )}
        </div>
      ))}
      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => setItems((prev) => [...prev, { productId: '', quantity: '', unitAmount: '' }])}
      >
        + Agregar ítem
      </button>

      <button className="btn" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Confirmando…' : 'Confirmar y registrar'}
      </button>
    </form>
  )
}

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const documentId = Number(id)
  const { activeCompany } = useCompany()
  const companyId = activeCompany!.id
  const navigate = useNavigate()

  const [doc, setDoc] = useState<MagaviDocument | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [confirmedResult, setConfirmedResult] = useState<Sale | Purchase | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const load = () => {
      documentsApi
        .detail(companyId, documentId)
        .then((fetchedDoc) => {
          if (cancelled) return
          setDoc(fetchedDoc)
          if (POLL_STATUSES.has(fetchedDoc.status)) {
            timer = setTimeout(load, POLL_INTERVAL_MS)
          }
        })
        .catch((err) => {
          if (!cancelled) setError(extractErrorMessage(err))
        })
    }
    load()
    productsApi.list(companyId).then(setProducts).catch(() => undefined)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [companyId, documentId])

  const handleReject = async () => {
    setError(null)
    try {
      await documentsApi.reject(companyId, documentId)
      const refreshed = await documentsApi.detail(companyId, documentId)
      setDoc(refreshed)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  if (error) return <ErrorBanner message={error} />
  if (!doc) return <FullScreenSpinner label="Cargando documento…" />

  return (
    <div className="stack">
      <button className="btn btn-secondary" type="button" onClick={() => navigate('/documents')}>
        ← Volver
      </button>
      <h1>Documento #{doc.id}</h1>
      <img
        src={doc.image}
        alt="Documento subido"
        style={{ width: '100%', borderRadius: 'var(--radius)', maxHeight: 320, objectFit: 'contain', background: 'var(--color-surface)' }}
      />

      {(doc.status === 'uploaded' || doc.status === 'processing') && (
        <p>⏳ Procesando el documento (OCR + estructuración)…</p>
      )}

      {doc.status === 'failed' && (
        <ErrorBanner message="No se pudo procesar este documento. Puedes rechazarlo y volver a intentar con otra foto." />
      )}

      {doc.extraction && (
        <details className="card">
          <summary>Texto detectado (OCR)</summary>
          <pre className="result-json">{doc.extraction.raw_ocr_text || '(sin texto)'}</pre>
        </details>
      )}

      {doc.status === 'needs_review' && (
        <ConfirmForm
          companyId={companyId}
          doc={doc}
          products={products}
          onDone={(result) => {
            setConfirmedResult(result)
            documentsApi.detail(companyId, documentId).then(setDoc)
          }}
        />
      )}

      {doc.status === 'needs_review' && (
        <button className="btn btn-danger btn-block" type="button" onClick={handleReject}>
          Rechazar (no registrar nada)
        </button>
      )}

      {doc.status === 'confirmed' && (
        <div className="card">
          <strong>✅ Confirmado</strong>
          {confirmedResult && <ResultView result={confirmedResult} />}
        </div>
      )}

      {doc.status === 'rejected' && <p>Este documento fue rechazado, no se registró nada.</p>}
    </div>
  )
}
