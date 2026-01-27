// ============================================================================
// Forecast API
// ============================================================================

import api from './client';
import type {
  ForecastResponse,
  ScenarioBarResponse,
  TransactionsResponse,
  CustomScenarioRequest,
  CustomScenarioResponse,
} from './types';

export async function getForecast(userId: string, weeks: number = 13): Promise<ForecastResponse> {
  return api.get<ForecastResponse>('/forecast', { user_id: userId, weeks: weeks.toString() });
}

/**
 * Get scenario bar metrics (runway, payroll safety, VAT reserve)
 */
export async function getScenarioBarMetrics(
  userId: string,
  timeRange: '13w' | '26w' | '52w' = '13w',
  scenarioId?: string
): Promise<ScenarioBarResponse> {
  const params: Record<string, string> = {
    user_id: userId,
    time_range: timeRange,
  };
  if (scenarioId) {
    params.scenario_id = scenarioId;
  }
  return api.get<ScenarioBarResponse>('/forecast/scenario-bar', params);
}

/**
 * Get forecast transactions (inflows or outflows) for display in tables
 */
export async function getTransactions(
  userId: string,
  type: 'inflows' | 'outflows',
  timeRange: '13w' | '26w' | '52w' = '13w'
): Promise<TransactionsResponse> {
  return api.get<TransactionsResponse>('/forecast/transactions', {
    user_id: userId,
    type,
    time_range: timeRange,
  });
}

/**
 * Create a custom scenario from transaction toggles
 */
export async function createCustomScenario(
  request: CustomScenarioRequest
): Promise<CustomScenarioResponse> {
  return api.post<CustomScenarioResponse>('/scenarios/custom', request);
}
