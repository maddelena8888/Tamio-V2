// ============================================================================
// Behavior Insights API Client
// ============================================================================

import api from './client';
import type {
  BehaviorInsightsResponse,
  BehaviorMetric,
  TriggeredScenario,
  TriggeredScenarioAction,
} from './types';

/**
 * Get complete behavior insights for a user.
 * Includes client behavior, expense behavior, cash discipline, and triggered scenarios.
 */
export async function getBehaviorInsights(
  userId: string,
  bufferMonths: number = 3
): Promise<BehaviorInsightsResponse> {
  return api.get<BehaviorInsightsResponse>('/behavior/insights', {
    user_id: userId,
    buffer_months: bufferMonths.toString(),
  });
}

/**
 * Get stored behavior metrics for a user.
 * @param metricType - Optional filter by metric type (e.g., 'payment_reliability')
 * @param entityType - Optional filter by entity type (e.g., 'client')
 */
export async function getBehaviorMetrics(
  userId: string,
  metricType?: string,
  entityType?: string
): Promise<BehaviorMetric[]> {
  const params: Record<string, string> = { user_id: userId };
  if (metricType) params.metric_type = metricType;
  if (entityType) params.entity_type = entityType;

  return api.get<BehaviorMetric[]>('/behavior/metrics', params);
}

/**
 * Get active triggers for a user.
 */
export async function getBehaviorTriggers(userId: string): Promise<
  Array<{
    id: string;
    name: string;
    description: string;
    conditions: Record<string, unknown>;
    scenario_template: Record<string, unknown>;
    recommended_actions: string[];
    severity: string;
    priority: number;
    is_active: boolean;
    cooldown_hours: number;
    last_triggered_at: string | null;
  }>
> {
  return api.get('/behavior/triggers', { user_id: userId });
}

/**
 * Toggle a trigger's active state.
 */
export async function toggleTrigger(
  triggerId: string
): Promise<{ id: string; is_active: boolean }> {
  return api.post(`/behavior/triggers/${triggerId}/toggle`);
}

/**
 * Get triggered scenarios for a user.
 * @param status - Optional filter by status (e.g., 'pending')
 */
export async function getTriggeredScenarios(
  userId: string,
  status?: string
): Promise<TriggeredScenario[]> {
  const params: Record<string, string> = { user_id: userId };
  if (status) params.status = status;

  return api.get<TriggeredScenario[]>('/behavior/triggered-scenarios', params);
}

/**
 * Respond to a triggered scenario.
 * @param action - 'run_scenario' | 'dismiss' | 'defer'
 */
export async function respondToTriggeredScenario(
  scenarioId: string,
  action: TriggeredScenarioAction
): Promise<{
  id: string;
  status: string;
  user_response: string;
  responded_at: string;
}> {
  return api.post(`/behavior/triggered-scenarios/${scenarioId}/respond`, action);
}

/**
 * Get detailed recommended actions for a triggered scenario.
 */
export async function getScenarioActions(
  scenarioId: string
): Promise<
  Array<{
    action_type: string;
    description: string;
    urgency: string;
    automated: boolean;
    parameters: Record<string, unknown>;
  }>
> {
  return api.get(`/behavior/triggered-scenarios/${scenarioId}/actions`);
}

/**
 * Get estimated impact for a triggered scenario.
 */
export async function getScenarioImpact(scenarioId: string): Promise<{
  cash_impact: number;
  cash_impact_weekly: number;
  weeks_affected: number;
  buffer_impact_pct: number;
  risk_delta: number;
  description: string;
}> {
  return api.get(`/behavior/triggered-scenarios/${scenarioId}/impact`);
}

/**
 * Generate a full scenario from a triggered scenario.
 * This creates a Scenario that can be run through the forecast engine.
 */
export async function generateScenarioFromTrigger(scenarioId: string): Promise<{
  triggered_scenario_id: string;
  trigger_name: string;
  scenario_preview: {
    name: string;
    description: string;
    scenario_type: string;
    scope_config: Record<string, unknown>;
    parameters: Record<string, unknown>;
  };
  recommended_actions: string[];
  severity: string;
  estimated_impact: Record<string, unknown> | null;
}> {
  return api.post(`/behavior/triggered-scenarios/${scenarioId}/generate`);
}
