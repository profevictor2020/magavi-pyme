import { getStoredCompanyId } from './companyStore'
import { clearTokens, getAccessToken, getRefreshToken, setAccessToken } from './tokenStore'

// Ver docs/ARCHITECTURE.md #3.1 y docker-compose.yml: en dev, frontend
// (5173) y backend (8000) son orígenes distintos (CORS ya permite
// localhost:5173, ver DJANGO_CORS_ALLOWED_ORIGINS). VITE_API_BASE_URL
// permite apuntar a otro backend (p.ej. detrás de nginx en producción).
const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000/api'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(typeof body === 'string' ? body : `Error ${status}`)
    this.status = status
    this.body = body
  }
}

export class AuthRequiredError extends Error {}

let onAuthRequired: (() => void) | null = null

/** Registrado por AuthProvider para reaccionar (redirigir a /login) cuando
 * el refresh también falla — ver AuthContext.tsx. */
export function setAuthRequiredHandler(handler: (() => void) | null): void {
  onAuthRequired = handler
}

interface RequestOptions {
  method?: string
  body?: unknown
  /** Empresa activa a enviar en X-Company-Id; por defecto la seleccionada. */
  companyId?: string | number | null
  /** Login/registro/refresh no llevan Authorization. */
  skipAuth?: boolean
  /** Endpoints que no dependen de una empresa (auth, companies). */
  skipCompany?: boolean
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken()
  if (!refresh) return null

  const response = await fetch(`${API_BASE_URL}/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })
  if (!response.ok) return null

  const data = (await response.json()) as { access: string }
  setAccessToken(data.access)
  return data.access
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = 'GET', body, companyId, skipAuth = false, skipCompany = false } = options
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData

  const buildHeaders = (accessToken: string | null): Record<string, string> => {
    const headers: Record<string, string> = {}
    if (!isFormData) headers['Content-Type'] = 'application/json'
    if (!skipAuth && accessToken) headers.Authorization = `Bearer ${accessToken}`
    if (!skipCompany) {
      const activeCompany = companyId ?? getStoredCompanyId()
      if (activeCompany) headers['X-Company-Id'] = String(activeCompany)
    }
    return headers
  }

  const doFetch = (accessToken: string | null) =>
    fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: buildHeaders(accessToken),
      body:
        body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
    })

  let response = await doFetch(getAccessToken())

  if (response.status === 401 && !skipAuth) {
    const newAccess = await refreshAccessToken()
    if (newAccess) {
      response = await doFetch(newAccess)
    } else {
      clearTokens()
      onAuthRequired?.()
      throw new AuthRequiredError('Sesión expirada, inicia sesión de nuevo.')
    }
  }

  if (response.status === 204) return undefined as T

  const contentType = response.headers.get('content-type') ?? ''
  const data: unknown = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    throw new ApiError(response.status, data)
  }

  return data as T
}

/** Extrae un mensaje de error legible desde el cuerpo de un ApiError
 * (DRF usa formas variadas: {"detail": "..."}, {"campo": ["msg"]}, ["msg"]). */
export function extractErrorMessage(error: unknown): string {
  if (error instanceof AuthRequiredError) return error.message
  if (!(error instanceof ApiError)) return 'Ocurrió un error inesperado.'

  const body = error.body
  if (typeof body === 'string' && body) return body
  if (body && typeof body === 'object') {
    if ('detail' in body && typeof (body as { detail?: unknown }).detail === 'string') {
      return (body as { detail: string }).detail
    }
    const values = Object.values(body as Record<string, unknown>)
    const firstMessages = values.flatMap((value) => (Array.isArray(value) ? value : [value]))
    const text = firstMessages.filter((value) => typeof value === 'string').join(' ')
    if (text) return text
  }
  return `Error ${error.status}`
}
