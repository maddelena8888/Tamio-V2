// ============================================================================
// Insights API Client
// ============================================================================

import api from './client';
import type {
  InsightsResponse,
  IncomeBehaviourInsights,
  ExpenseBehaviourInsights,
  CashDisciplineInsights,
  InsightsSummary,
} from './types';

/**
 * Get complete insights for a user.
 */
export async function getInsights(
  userId: string,
  bufferMonths: number = 3
): Promise<InsightsResponse> {
  return api.get<InsightsResponse>('/insights', {
    user_id: userId,
    buffer_months: bufferMonths.toString(),
  });
}

/**
 * Get income behaviour insights only.
 */
export async function getIncomeInsights(
  userId: string
): Promise<IncomeBehaviourInsights> {
  return api.get<IncomeBehaviourInsights>('/insights/income', {
    user_id: userId,
  });
}

/**
 * Get expense behaviour insights only.
 */
export async function getExpenseInsights(
  userId: string
): Promise<ExpenseBehaviourInsights> {
  return api.get<ExpenseBehaviourInsights>('/insights/expenses', {
    user_id: userId,
  });
}

/**
 * Get cash discipline insights only.
 */
export async function getCashDisciplineInsights(
  userId: string,
  bufferMonths: number = 3
): Promise<CashDisciplineInsights> {
  return api.get<CashDisciplineInsights>('/insights/cash-discipline', {
    user_id: userId,
    buffer_months: bufferMonths.toString(),
  });
}

/**
 * Get insights summary with health scores only.
 */
export async function getInsightsSummary(
  userId: string
): Promise<InsightsSummary> {
  return api.get<InsightsSummary>('/insights/summary', {
    user_id: userId,
  });
}
