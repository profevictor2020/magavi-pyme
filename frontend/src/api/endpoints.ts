import { apiFetch } from './client'
import type {
  CashboxSummary,
  ChatResponse,
  Company,
  ConfirmIntentResponse,
  Conversation,
  InventoryMovement,
  MagaviDocument,
  Message,
  PeriodSummary,
  Product,
  Purchase,
  Sale,
  User,
} from './types'

interface AuthTokens {
  access: string
  refresh: string
}

export const authApi = {
  login: (email: string, password: string) =>
    apiFetch<AuthTokens>('/auth/login/', {
      method: 'POST',
      body: { email, password },
      skipAuth: true,
      skipCompany: true,
    }),
  register: (email: string, password: string, firstName: string) =>
    apiFetch<AuthTokens & { user: User }>('/auth/register/', {
      method: 'POST',
      body: { email, password, first_name: firstName },
      skipAuth: true,
      skipCompany: true,
    }),
  me: () => apiFetch<User>('/auth/me/', { skipCompany: true }),
}

export const companiesApi = {
  list: () => apiFetch<Company[]>('/companies/', { skipCompany: true }),
  create: (name: string, rut: string) =>
    apiFetch<Company>('/companies/', { method: 'POST', body: { name, rut }, skipCompany: true }),
}

// Todos los endpoints de negocio reciben `companyId` explícito (la
// empresa activa desde CompanyContext) en vez de depender del valor
// guardado en localStorage al momento del fetch: los efectos de React
// que persisten la selección y los que disparan estas llamadas no
// tienen un orden garantizado entre sí, así que pasar el id a mano
// evita una condición de carrera real entre ambos.

export const productsApi = {
  list: (companyId: number, lowStock = false) =>
    apiFetch<Product[]>(`/products/${lowStock ? '?low_stock=true' : ''}`, { companyId }),
  create: (
    companyId: number,
    data: {
      name: string
      sku?: string
      unit: string
      default_price: string
      default_cost: string
      low_stock_threshold?: string
      initial_stock?: string
    },
  ) => apiFetch<Product>('/products/', { method: 'POST', body: data, companyId }),
  adjustStock: (companyId: number, productId: number, cantidad: string, motivo: string) =>
    apiFetch<InventoryMovement>(`/products/${productId}/adjust-stock/`, {
      method: 'POST',
      body: { cantidad, motivo },
      companyId,
    }),
}

export const salesApi = {
  list: (companyId: number) => apiFetch<Sale[]>('/sales/', { companyId }),
  create: (
    companyId: number,
    data: {
      customer_name?: string
      items: { product_id: number; quantity: string; unit_price?: string }[]
    },
  ) => apiFetch<Sale>('/sales/', { method: 'POST', body: data, companyId }),
  summary: (companyId: number) =>
    apiFetch<{ today: PeriodSummary; week: PeriodSummary }>('/sales/summary/', { companyId }),
}

export const purchasesApi = {
  list: (companyId: number) => apiFetch<Purchase[]>('/purchases/', { companyId }),
  create: (
    companyId: number,
    data: {
      supplier_name?: string
      items: { product_id: number; quantity: string; unit_cost?: string }[]
    },
  ) => apiFetch<Purchase>('/purchases/', { method: 'POST', body: data, companyId }),
  summary: (companyId: number) =>
    apiFetch<{ today: PeriodSummary; week: PeriodSummary }>('/purchases/summary/', { companyId }),
}

export const cashboxApi = {
  summary: (companyId: number) => apiFetch<CashboxSummary>('/cashbox/summary/', { companyId }),
}

export const assistantApi = {
  chat: (companyId: number, message: string, conversationId?: number | null) =>
    apiFetch<ChatResponse>('/assistant/chat/', {
      method: 'POST',
      body: { message, conversation_id: conversationId ?? undefined },
      companyId,
    }),
  confirmIntent: (companyId: number, pendingActionId: number) =>
    apiFetch<ConfirmIntentResponse>(`/assistant/intents/${pendingActionId}/confirm/`, {
      method: 'POST',
      companyId,
    }),
  cancelIntent: (companyId: number, pendingActionId: number) =>
    apiFetch<{ status: string }>(`/assistant/intents/${pendingActionId}/cancel/`, {
      method: 'POST',
      companyId,
    }),
  conversations: (companyId: number) =>
    apiFetch<Conversation[]>('/assistant/conversations/', { companyId }),
  messages: (companyId: number, conversationId: number) =>
    apiFetch<Message[]>(`/assistant/conversations/${conversationId}/messages/`, { companyId }),
}

export const documentsApi = {
  list: (companyId: number) => apiFetch<MagaviDocument[]>('/documents/', { companyId }),
  detail: (companyId: number, id: number) =>
    apiFetch<MagaviDocument>(`/documents/${id}/`, { companyId }),
  upload: (companyId: number, file: File) => {
    const formData = new FormData()
    formData.append('image', file)
    return apiFetch<MagaviDocument>('/documents/', { method: 'POST', body: formData, companyId })
  },
  confirm: (
    companyId: number,
    id: number,
    data: {
      document_type: 'purchase' | 'sale'
      party_name?: string
      items: { product_id: number; quantity: string; unit_amount?: string }[]
    },
  ) =>
    apiFetch<{ status: string; document_type: string; result: Sale | Purchase }>(
      `/documents/${id}/confirm/`,
      { method: 'POST', body: data, companyId },
    ),
  reject: (companyId: number, id: number) =>
    apiFetch<{ status: string }>(`/documents/${id}/reject/`, { method: 'POST', companyId }),
}
