import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { authApi } from '../api/endpoints'
import { setAuthRequiredHandler } from '../api/client'
import { clearTokens, getAccessToken, setTokens } from '../api/tokenStore'
import { clearStoredCompanyId } from '../api/companyStore'
import type { User } from '../api/types'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, firstName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const logout = useCallback(() => {
    clearTokens()
    clearStoredCompanyId()
    setUser(null)
  }, [])

  useEffect(() => {
    setAuthRequiredHandler(logout)
    return () => setAuthRequiredHandler(null)
  }, [logout])

  useEffect(() => {
    if (!getAccessToken()) {
      setIsLoading(false)
      return
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        clearTokens()
      })
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authApi.login(email, password)
    setTokens(tokens.access, tokens.refresh)
    const me = await authApi.me()
    setUser(me)
  }, [])

  const register = useCallback(async (email: string, password: string, firstName: string) => {
    const data = await authApi.register(email, password, firstName)
    setTokens(data.access, data.refresh)
    setUser(data.user)
  }, [])

  const value = useMemo(
    () => ({ user, isLoading, login, register, logout }),
    [user, isLoading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return context
}
