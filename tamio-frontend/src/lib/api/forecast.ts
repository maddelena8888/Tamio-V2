// ============================================================================
// Forecast API
// ============================================================================

import api from './client';
import type { ForecastResponse } from './types';

export async function getForecast(userId: string, weeks: number = 13): Promise<ForecastResponse> {
  return api.get<ForecastResponse>('/forecast', { user_id: userId, weeks: weeks.toString() });
}
