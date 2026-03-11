/**
 * E-Invoice API Client - Taiwan Electronic Invoice (電子發票)
 */
import apiClient from './client'

// Types
export interface InvoiceItemInput {
  item_name: string
  item_count: number
  item_unit: string
  item_price: number
  item_amount?: number
  item_tax_type?: 'taxable' | 'zero_tax' | 'tax_free' | 'mixed'
}

export interface B2CInvoiceRequest {
  order_id: string
  buyer_email?: string
  tax_type: 'taxable' | 'zero_tax' | 'tax_free' | 'mixed'
  carrier_type?: 'mobile_barcode' | 'citizen_cert' | 'email' | null
  carrier_number?: string | null
  is_donation: boolean
  love_code?: string | null
  items: InvoiceItemInput[]
}

export interface B2BInvoiceRequest {
  order_id: string
  buyer_company_name: string
  buyer_tax_id: string
  buyer_email?: string
  tax_type: 'taxable' | 'zero_tax' | 'tax_free' | 'mixed'
  items: InvoiceItemInput[]
}

export interface VoidInvoiceRequest {
  invoice_id: string
  reason: string
}

export interface InvoicePrefs {
  default_carrier_type?: 'mobile_barcode' | 'citizen_cert' | 'email' | null
  default_carrier_number?: string | null
  default_love_code?: string | null
}

export interface EInvoiceDetail {
  id: string
  order_id: string | null
  invoice_number: string | null
  invoice_type: 'b2c' | 'b2b'
  amount: number
  sales_amount: number | null
  tax_amount: number | null
  tax_type: string
  status: 'issued' | 'voided' | 'failed' | 'pending_issue'
  buyer_company_name?: string
  buyer_tax_id?: string
  buyer_email?: string
  carrier_type?: string
  is_donation: boolean
  love_code?: string
  issued_at: string | null
  voided_at: string | null
  void_reason?: string
  can_void: boolean
  items: {
    item_name: string
    item_count: number
    item_unit: string
    item_price: number
    item_amount: number
  }[]
}

export interface EInvoiceResponse {
  success: boolean
  invoice_id?: string
  invoice_number?: string
  message?: string
  error?: string
}

export interface InvoiceListResponse {
  success: boolean
  invoices: EInvoiceDetail[]
  total: number
  limit: number
  offset: number
}

// API methods
export const einvoiceApi = {
  async createB2C(request: B2CInvoiceRequest): Promise<EInvoiceResponse> {
    const { data } = await apiClient.post('/api/v1/einvoices/b2c', request)
    return data
  },

  async createB2B(request: B2BInvoiceRequest): Promise<EInvoiceResponse> {
    const { data } = await apiClient.post('/api/v1/einvoices/b2b', request)
    return data
  },

  async voidInvoice(invoiceId: string, reason: string): Promise<EInvoiceResponse> {
    const { data } = await apiClient.post('/api/v1/einvoices/void', {
      invoice_id: invoiceId,
      reason,
    })
    return data
  },

  async listInvoices(limit = 20, offset = 0): Promise<InvoiceListResponse> {
    const { data } = await apiClient.get('/api/v1/einvoices', {
      params: { limit, offset },
    })
    return data
  },

  async getInvoice(invoiceId: string): Promise<{ success: boolean; invoice: EInvoiceDetail }> {
    const { data } = await apiClient.get(`/api/v1/einvoices/${invoiceId}`)
    return data
  },

  async updatePreferences(prefs: InvoicePrefs): Promise<{ success: boolean; message: string }> {
    const { data } = await apiClient.put('/api/v1/einvoices/preferences', prefs)
    return data
  },
}

export default einvoiceApi
