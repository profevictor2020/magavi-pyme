import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useCompany } from '../context/CompanyContext'
import { FullScreenSpinner } from './Spinner'

/** Exige sesión iniciada; no exige una empresa activa todavía (usado por
 * /companies, a la que se debe poder llegar sin haber elegido una). */
export function RequireAuth() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullScreenSpinner />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

/** Exige además una empresa activa; si el usuario no tiene ninguna
 * empresa todavía, lo manda a crearla/elegirla primero. */
export function RequireCompany() {
  const { activeCompany, isLoading } = useCompany()

  if (isLoading) return <FullScreenSpinner />
  if (!activeCompany) return <Navigate to="/companies" replace />
  return <Outlet />
}
