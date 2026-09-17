// Espejo de los serializers del backend (ver backend/*/serializers.py).
// Los campos numéricos (Decimal) viajan como string en JSON — nunca se
// re-serializan como number para no perder precisión.

export interface User {
  id: number
  email: string
  first_name: string
}

export interface Company {
  id: number
  name: string
  rut: string
  is_active: boolean
  created_at: string
  role: 'owner' | 'admin' | 'staff' | null
}

export interface Product {
  id: number
  name: string
  sku: string | null
  unit: string
  default_price: string
  default_cost: string
  low_stock_threshold: string
  current_stock: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface InventoryMovement {
  id: number
  product: number
  type: 'in' | 'out'
  quantity: string
  reference_type: string
  reason: string
  balance_after: string
  created_by: number | null
  created_at: string
}

export interface SaleItem {
  id: number
  product: number
  quantity: string
  unit_price: string
  subtotal: string
}

export interface Sale {
  id: number
  sold_at: string
  customer_name: string
  total: string
  status: string
  source: string
  created_at: string
  items: SaleItem[]
}

export interface PurchaseItem {
  id: number
  product: number
  quantity: string
  unit_cost: string
  subtotal: string
}

export interface Purchase {
  id: number
  purchased_at: string
  supplier_name: string
  total: string
  status: string
  source: string
  created_at: string
  items: PurchaseItem[]
}

export interface PeriodSummary {
  total: string
  count: number
}

export interface CashPeriodSummary {
  income: string
  expense: string
  balance: string
}

export interface LowStockProduct {
  id: number
  name: string
  current_stock: string
  low_stock_threshold: string
}

export interface CashboxSummary {
  cash: { today: CashPeriodSummary; week: CashPeriodSummary }
  sales: { today: PeriodSummary; week: PeriodSummary }
  low_stock_products: LowStockProduct[]
}

export type DocumentStatus =
  | 'uploaded'
  | 'processing'
  | 'needs_review'
  | 'confirmed'
  | 'rejected'
  | 'failed'

export type DocumentTypeGuess = 'purchase' | 'sale' | 'unknown'

export interface DocumentExtractionItem {
  product_id: number | null
  product_name_raw?: string
  quantity: string
  unit_price?: string
}

export interface DocumentExtractionData {
  document_type: DocumentTypeGuess
  counterparty_name?: string
  date?: string
  items: DocumentExtractionItem[]
  total?: string | null
}

export interface DocumentExtraction {
  raw_ocr_text: string
  structured_data: DocumentExtractionData
  confidence: string
  reviewed_by: number | null
  reviewed_at: string | null
  created_at: string
}

export interface MagaviDocument {
  id: number
  image: string
  status: DocumentStatus
  document_type_guess: DocumentTypeGuess
  created_at: string
  updated_at: string
  extraction: DocumentExtraction | null
}

export interface Conversation {
  id: number
  started_at: string
  last_message_at: string
}

export interface Message {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  structured_intent: Record<string, unknown> | null
  created_at: string
}

export type ChatResult =
  | { status: 'no_entendido'; message: string }
  | { status: 'error'; message: string }
  | { status: 'answered'; message: string }
  | { status: 'executed'; result: unknown }
  | {
      status: 'pending_confirmation'
      pending_action_id: number
      intent: string
      parameters: Record<string, unknown>
      expires_at: string
    }

export type ChatResponse = { conversation_id: number } & ChatResult

export interface ConfirmIntentResponse {
  status: 'confirmed'
  result: Sale | Purchase | InventoryMovement | Record<string, unknown>
}
