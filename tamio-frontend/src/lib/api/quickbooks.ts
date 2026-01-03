// ============================================================================
// QuickBooks Integration API
// ============================================================================

import api from './client';

// QuickBooks-specific types
export interface QuickBooksConnectionStatus {
  is_connected: boolean;
  company_name: string | null;
  realm_id: string | null;
  last_sync_at: string | null;
  token_expires_at: string | null;
  refresh_token_expires_at: string | null;
  sync_error: string | null;
}

export interface QuickBooksAuthUrl {
  auth_url: string;
  state: string;
}

export interface QuickBooksSyncResult {
  success: boolean;
  message: string;
  records_fetched: Record<string, number>;
  records_created: Record<string, number>;
  records_updated: Record<string, number>;
  errors: string[];
}

export interface QuickBooksPreview {
  company_info: {
    company_id: string;
    company_name: string;
    legal_name: string | null;
    country: string | null;
    currency: string | null;
  };
  summary: {
    customers: number;
    outstanding_invoices: number;
    receivables_total: number;
    vendors: number;
    outstanding_bills: number;
    payables_total: number;
  };
  bank_summary: {
    accounts: Array<{
      account_id: string;
      name: string;
      current_balance: number;
    }>;
    total_balance: number;
  };
  customers: Array<{
    customer_id: string;
    display_name: string;
    email: string | null;
    balance: number;
  }>;
  invoices: Array<{
    invoice_id: string;
    doc_number: string | null;
    customer_name: string;
    balance: number;
    total_amount: number;
    due_date: string | null;
  }>;
  vendors: Array<{
    vendor_id: string;
    display_name: string;
    email: string | null;
    balance: number;
  }>;
  bills: Array<{
    bill_id: string;
    doc_number: string | null;
    vendor_name: string;
    balance: number;
    total_amount: number;
    due_date: string | null;
  }>;
}

export interface QuickBooksSyncLog {
  id: string;
  sync_type: string;
  status: string;
  records_fetched: Record<string, number> | null;
  records_created: Record<string, number> | null;
  records_updated: Record<string, number> | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

// API Functions

export async function getQuickBooksStatus(userId: string): Promise<QuickBooksConnectionStatus> {
  return api.get<QuickBooksConnectionStatus>('/quickbooks/status', { user_id: userId });
}

export async function getQuickBooksConnectUrl(userId: string): Promise<QuickBooksAuthUrl> {
  return api.get<QuickBooksAuthUrl>('/quickbooks/connect', { user_id: userId });
}

export async function disconnectQuickBooks(userId: string): Promise<{ success: boolean; message: string }> {
  return api.post(`/quickbooks/disconnect?user_id=${userId}`);
}

export async function syncQuickBooks(
  userId: string,
  syncType: 'full' | 'incremental' | 'invoices' | 'customers' = 'full'
): Promise<QuickBooksSyncResult> {
  return api.post<QuickBooksSyncResult>('/quickbooks/sync', {
    user_id: userId,
    sync_type: syncType,
  });
}

export async function getQuickBooksPreview(userId: string): Promise<QuickBooksPreview> {
  return api.get<QuickBooksPreview>('/quickbooks/preview', { user_id: userId });
}

export async function getQuickBooksPaymentAnalysis(userId: string): Promise<unknown> {
  return api.get('/quickbooks/payment-analysis', { user_id: userId });
}

export async function getQuickBooksSyncHistory(
  userId: string,
  limit: number = 10
): Promise<{ sync_logs: QuickBooksSyncLog[] }> {
  return api.get('/quickbooks/sync-history', { user_id: userId, limit: String(limit) });
}
