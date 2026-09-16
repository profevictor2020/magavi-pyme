import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { documentsApi } from '../api/endpoints'
import { extractErrorMessage } from '../api/client'
import { useCompany } from '../context/CompanyContext'
import type { MagaviDocument } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { FullScreenSpinner } from '../components/Spinner'
import { formatDateTime } from '../lib/format'

const STATUS_LABELS: Record<MagaviDocument['status'], string> = {
  uploaded: 'Subido',
  processing: 'Procesando…',
  needs_review: 'Por revisar',
  confirmed: 'Confirmado',
  rejected: 'Rechazado',
  failed: 'Falló',
}

export function DocumentsPage() {
  const { activeCompany } = useCompany()
  const companyId = activeCompany!.id
  const navigate = useNavigate()
  const [documents, setDocuments] = useState<MagaviDocument[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    setError(null)
    documentsApi
      .list(companyId)
      .then((list) => setDocuments(list.sort((a, b) => b.id - a.id)))
      .catch((err) => setError(extractErrorMessage(err)))
  }, [companyId])

  useEffect(() => {
    setDocuments(null)
    load()
  }, [load])

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setError(null)
    setIsUploading(true)
    try {
      const document = await documentsApi.upload(companyId, file)
      navigate(`/documents/${document.id}`)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="stack">
      <h1>Documentos</h1>
      <p style={{ color: 'var(--color-muted)' }}>
        Fotografía una boleta o factura: la revisamos y confirmamos juntos antes de registrar
        nada.
      </p>
      <ErrorBanner message={error} />

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={handleFileChange}
      />
      <button
        className="btn btn-block"
        type="button"
        disabled={isUploading}
        onClick={() => fileInputRef.current?.click()}
      >
        {isUploading ? 'Subiendo…' : '📸 Fotografiar documento'}
      </button>

      {documents === null && <FullScreenSpinner label="Cargando documentos…" />}
      {documents?.length === 0 && <p>No hay documentos subidos todavía.</p>}
      {documents?.map((document) => (
        <button
          key={document.id}
          type="button"
          className="card"
          style={{ textAlign: 'left', display: 'flex', gap: 'var(--space-3)' }}
          onClick={() => navigate(`/documents/${document.id}`)}
        >
          <img
            src={document.image}
            alt=""
            style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 8 }}
          />
          <div>
            <strong>{STATUS_LABELS[document.status]}</strong>
            <div style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
              {formatDateTime(document.created_at)}
            </div>
          </div>
        </button>
      ))}
    </div>
  )
}
