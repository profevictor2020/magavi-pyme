import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useCompany } from '../context/CompanyContext'
import { extractErrorMessage } from '../api/client'
import { ErrorBanner } from '../components/ErrorBanner'

export function CompanyPage() {
  const { logout } = useAuth()
  const { companies, activeCompany, selectCompany, createCompany } = useCompany()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [rut, setRut] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await createCompany(name, rut)
      navigate('/', { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="centered-screen">
      <h1>Tu empresa</h1>

      {companies.length > 0 && (
        <div className="stack" style={{ marginBottom: 'var(--space-5)' }}>
          <p style={{ color: 'var(--color-muted)' }}>Empresas donde tienes acceso:</p>
          {companies.map((company) => (
            <button
              key={company.id}
              type="button"
              className="card"
              style={{
                textAlign: 'left',
                border:
                  company.id === activeCompany?.id
                    ? '2px solid var(--color-primary)'
                    : undefined,
              }}
              onClick={() => {
                selectCompany(company.id)
                navigate('/', { replace: true })
              }}
            >
              <strong>{company.name}</strong>
              <div style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
                {company.rut} · {company.role}
              </div>
            </button>
          ))}
        </div>
      )}

      <form className="stack" onSubmit={handleCreate}>
        <p style={{ color: 'var(--color-muted)' }}>
          {companies.length > 0 ? 'O crea una empresa nueva:' : 'Crea tu primera empresa:'}
        </p>
        <ErrorBanner message={error} />
        <div className="field">
          <label htmlFor="companyName">Nombre del negocio</label>
          <input id="companyName" required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="companyRut">RUT</label>
          <input id="companyRut" required value={rut} onChange={(e) => setRut(e.target.value)} />
        </div>
        <button className="btn btn-block" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creando…' : 'Crear empresa'}
        </button>
      </form>

      <button
        type="button"
        className="btn btn-secondary btn-block"
        style={{ marginTop: 'var(--space-5)' }}
        onClick={logout}
      >
        Cerrar sesión
      </button>
    </div>
  )
}
