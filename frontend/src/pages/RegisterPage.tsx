import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../api/client'
import { ErrorBanner } from '../components/ErrorBanner'

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [firstName, setFirstName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register(email, password, firstName)
      navigate('/', { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="centered-screen">
      <h1>Crear cuenta</h1>
      <form className="stack" onSubmit={handleSubmit}>
        <ErrorBanner message={error} />
        <div className="field">
          <label htmlFor="firstName">Nombre</label>
          <input
            id="firstName"
            required
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="email">Correo electrónico</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Contraseña</label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button className="btn btn-block" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creando…' : 'Crear cuenta'}
        </button>
      </form>
      <p style={{ marginTop: 'var(--space-4)', textAlign: 'center' }}>
        ¿Ya tienes cuenta? <Link to="/login">Ingresa</Link>
      </p>
    </div>
  )
}
