// ============================================================================
// Onboarding API
// ============================================================================

import api from './client';
import type { OnboardingRequest, OnboardingResponse } from './types';

export async function completeOnboarding(
  data: OnboardingRequest
): Promise<OnboardingResponse> {
  return api.post<OnboardingResponse>('/data/onboarding', data);
}

// Step-by-step onboarding endpoints
export async function startOnboarding(): Promise<{ session_id: string }> {
  return api.post('/data/onboarding/start');
}

export async function saveCashPosition(
  userId: string,
  accounts: Array<{
    account_name: string;
    balance: string;
    currency: string;
    as_of_date: string;
  }>
): Promise<unknown> {
  return api.post('/data/onboarding/save-cash-position', {
    user_id: userId,
    accounts,
  });
}

export async function addOnboardingClient(
  userId: string,
  client: {
    name: string;
    client_type: string;
    currency: string;
    status: string;
    billing_config: Record<string, unknown>;
  }
): Promise<unknown> {
  return api.post('/data/onboarding/add-client', {
    user_id: userId,
    ...client,
  });
}

export async function addOnboardingExpense(
  userId: string,
  expense: {
    name: string;
    category: string;
    bucket_type: string;
    monthly_amount: string;
    currency: string;
    priority: string;
  }
): Promise<unknown> {
  return api.post('/data/onboarding/add-expense', {
    user_id: userId,
    ...expense,
  });
}

export async function finishOnboarding(userId: string): Promise<unknown> {
  return api.post(`/data/onboarding/complete?user_id=${userId}`);
}
