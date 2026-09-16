const COMPANY_KEY = 'magavi.companyId'

export function getStoredCompanyId(): string | null {
  try {
    return localStorage.getItem(COMPANY_KEY)
  } catch {
    return null
  }
}

export function setStoredCompanyId(companyId: string): void {
  try {
    localStorage.setItem(COMPANY_KEY, companyId)
  } catch {
    // ver tokenStore.ts
  }
}

export function clearStoredCompanyId(): void {
  try {
    localStorage.removeItem(COMPANY_KEY)
  } catch {
    // ver tokenStore.ts
  }
}
