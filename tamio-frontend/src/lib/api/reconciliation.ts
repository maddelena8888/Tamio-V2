// ============================================================================
// Reconciliation API
// ============================================================================

import api from './client';
import type {
  ReconciliationSuggestionList,
  ApproveReconciliationRequest,
  BulkReconciliationRequest,
  BulkReconciliationResult,
  RejectReconciliationRequest,
  RevertReconciliationRequest,
  ForecastImpactSummary,
  ReconciliationQueueSummary,
  PaymentEvent,
} from './types';

/**
 * Get AI-generated suggestions for matching unreconciled payments to schedules.
 */
export async function getReconciliationSuggestions(
  includeAutoApproved: boolean = false
): Promise<ReconciliationSuggestionList> {
  return api.get<ReconciliationSuggestionList>('/reconciliation/suggestions', {
    include_auto_approved: includeAutoApproved.toString(),
  });
}

/**
 * Approve a single reconciliation suggestion or manual match.
 */
export async function approveReconciliation(
  request: ApproveReconciliationRequest
): Promise<PaymentEvent> {
  return api.post<PaymentEvent>('/reconciliation/approve', request);
}

/**
 * Approve multiple reconciliation matches at once.
 */
export async function approveBulkReconciliation(
  request: BulkReconciliationRequest
): Promise<BulkReconciliationResult> {
  return api.post<BulkReconciliationResult>('/reconciliation/approve-bulk', request);
}

/**
 * Reject a reconciliation suggestion.
 */
export async function rejectReconciliation(
  request: RejectReconciliationRequest
): Promise<PaymentEvent> {
  return api.post<PaymentEvent>('/reconciliation/reject', request);
}

/**
 * Revert an auto-approved or manually approved reconciliation.
 */
export async function revertReconciliation(
  request: RevertReconciliationRequest
): Promise<PaymentEvent> {
  return api.post<PaymentEvent>('/reconciliation/revert', request);
}

/**
 * Get forecast accuracy impact from unreconciled items.
 */
export async function getForecastImpact(): Promise<ForecastImpactSummary> {
  return api.get<ForecastImpactSummary>('/reconciliation/forecast-impact');
}

/**
 * Get recently auto-approved reconciliations for audit/review.
 */
export async function getAutoApproved(
  hours: number = 24
): Promise<PaymentEvent[]> {
  return api.get<PaymentEvent[]>('/reconciliation/auto-approved', {
    hours: hours.toString(),
  });
}

/**
 * Get reconciliation queue summary for UI display.
 */
export async function getQueueSummary(): Promise<ReconciliationQueueSummary> {
  return api.get<ReconciliationQueueSummary>('/reconciliation/queue-summary');
}

/**
 * Get all unreconciled payments.
 */
export async function getUnreconciledPayments(): Promise<PaymentEvent[]> {
  return api.get<PaymentEvent[]>('/reconciliation/unreconciled-payments');
}

/**
 * Get all payments for the transaction list view.
 */
export async function getAllPayments(
  fromDate?: string,
  toDate?: string,
  reconciledOnly: boolean = false
): Promise<PaymentEvent[]> {
  const params: Record<string, string> = {};
  if (fromDate) params.from_date = fromDate;
  if (toDate) params.to_date = toDate;
  if (reconciledOnly) params.reconciled_only = 'true';
  return api.get<PaymentEvent[]>('/payments', params);
}
