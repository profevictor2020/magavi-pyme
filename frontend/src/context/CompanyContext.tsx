import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { companiesApi } from '../api/endpoints'
import { getStoredCompanyId, setStoredCompanyId } from '../api/companyStore'
import type { Company } from '../api/types'
import { useAuth } from './AuthContext'

interface CompanyContextValue {
  companies: Company[]
  activeCompany: Company | null
  isLoading: boolean
  selectCompany: (companyId: number) => void
  createCompany: (name: string, rut: string) => Promise<Company>
  refresh: () => Promise<void>
}

const CompanyContext = createContext<CompanyContextValue | null>(null)

export function CompanyProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [companies, setCompanies] = useState<Company[]>([])
  const [activeCompanyId, setActiveCompanyId] = useState<number | null>(() => {
    const stored = getStoredCompanyId()
    return stored ? Number(stored) : null
  })
  const [isLoading, setIsLoading] = useState(true)

  const refresh = useCallback(async () => {
    const list = await companiesApi.list()
    setCompanies(list)
    setActiveCompanyId((current) => {
      if (current && list.some((c) => c.id === current)) return current
      return list[0]?.id ?? null
    })
  }, [])

  useEffect(() => {
    if (!user) {
      setCompanies([])
      setActiveCompanyId(null)
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    refresh().finally(() => setIsLoading(false))
  }, [user, refresh])

  useEffect(() => {
    if (activeCompanyId) setStoredCompanyId(String(activeCompanyId))
  }, [activeCompanyId])

  const selectCompany = useCallback((companyId: number) => {
    setActiveCompanyId(companyId)
  }, [])

  const createCompany = useCallback(async (name: string, rut: string) => {
    const company = await companiesApi.create(name, rut)
    setCompanies((prev) => [...prev, company])
    setActiveCompanyId(company.id)
    return company
  }, [])

  const activeCompany = useMemo(
    () => companies.find((c) => c.id === activeCompanyId) ?? null,
    [companies, activeCompanyId],
  )

  const value = useMemo(
    () => ({ companies, activeCompany, isLoading, selectCompany, createCompany, refresh }),
    [companies, activeCompany, isLoading, selectCompany, createCompany, refresh],
  )

  return <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>
}

export function useCompany(): CompanyContextValue {
  const context = useContext(CompanyContext)
  if (!context) throw new Error('useCompany debe usarse dentro de <CompanyProvider>')
  return context
}
