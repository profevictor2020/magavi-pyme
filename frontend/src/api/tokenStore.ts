// Guarda los tokens JWT en localStorage (ver docs/DECISIONS.md ADR-012:
// tradeoff aceptado para el MVP frente a cookies httpOnly).
const ACCESS_KEY = 'magavi.access'
const REFRESH_KEY = 'magavi.refresh'

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(ACCESS_KEY)
  } catch {
    return null
  }
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY)
  } catch {
    return null
  }
}

export function setTokens(access: string, refresh: string): void {
  try {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  } catch {
    // Almacenamiento no disponible (modo privado, cuota excedida, etc.):
    // la sesión simplemente no persistirá entre recargas.
  }
}

export function setAccessToken(access: string): void {
  try {
    localStorage.setItem(ACCESS_KEY, access)
  } catch {
    // ver setTokens
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  } catch {
    // ver setTokens
  }
}
