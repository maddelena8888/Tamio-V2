// ============================================================================
// Scenarios API
// ============================================================================

import api from './client';
import type {
  Scenario,
  ScenarioCreate,
  ScenarioComparisonResponse,
  ScenarioSuggestion,
  FinancialRule,
  RuleEvaluation,
} from './types';

// Financial Rules
export async function getRules(userId: string): Promise<FinancialRule[]> {
  return api.get<FinancialRule[]>('/scenarios/rules', { user_id: userId });
}

export async function createRule(rule: Omit<FinancialRule, 'id' | 'created_at' | 'updated_at'>): Promise<FinancialRule> {
  return api.post<FinancialRule>('/scenarios/rules', rule);
}

export async function updateRule(
  ruleId: string,
  updates: Partial<FinancialRule>
): Promise<FinancialRule> {
  return api.put<FinancialRule>(`/scenarios/rules/${ruleId}`, updates);
}

export async function deleteRule(ruleId: string): Promise<{ message: string }> {
  return api.delete<{ message: string }>(`/scenarios/rules/${ruleId}`);
}

// Scenarios
export async function getScenarios(
  userId: string,
  status?: string
): Promise<Scenario[]> {
  const params: Record<string, string> = { user_id: userId };
  if (status) params.status = status;
  return api.get<Scenario[]>('/scenarios/scenarios', params);
}

export async function getScenario(scenarioId: string): Promise<Scenario> {
  return api.get<Scenario>(`/scenarios/scenarios/${scenarioId}`);
}

export async function createScenario(scenario: ScenarioCreate): Promise<Scenario> {
  return api.post<Scenario>('/scenarios/scenarios', scenario);
}

export async function updateScenario(
  scenarioId: string,
  updates: Partial<ScenarioCreate>
): Promise<Scenario> {
  return api.put<Scenario>(`/scenarios/scenarios/${scenarioId}`, updates);
}

export async function deleteScenario(scenarioId: string): Promise<{ message: string }> {
  return api.delete<{ message: string }>(`/scenarios/scenarios/${scenarioId}`);
}

export async function buildScenario(scenarioId: string): Promise<{
  message: string;
  events_generated: number;
}> {
  return api.post(`/scenarios/scenarios/${scenarioId}/build`);
}

export async function addScenarioLayer(
  scenarioId: string,
  layer: {
    layer_type: string;
    layer_name: string;
    parameters: Record<string, unknown>;
  }
): Promise<{
  message: string;
  events_generated: number;
  total_layers: number;
  linked_scenarios: Scenario[];
}> {
  return api.post(`/scenarios/scenarios/${scenarioId}/add-layer`, layer);
}

export async function saveScenario(scenarioId: string): Promise<{
  message: string;
  scenario_id: string;
  scenario_name: string;
}> {
  return api.post(`/scenarios/scenarios/${scenarioId}/save`);
}

export async function getScenarioForecast(
  scenarioId: string
): Promise<ScenarioComparisonResponse> {
  return api.get<ScenarioComparisonResponse>(`/scenarios/scenarios/${scenarioId}/forecast`);
}

export async function getScenarioSuggestions(userId: string): Promise<{
  suggestions: ScenarioSuggestion[];
  based_on: {
    runway_weeks: number;
    has_rule_breaches: boolean;
  };
}> {
  return api.get('/scenarios/scenarios/suggest', { user_id: userId });
}

export async function evaluateBaseRules(userId: string): Promise<{
  evaluations: RuleEvaluation[];
  decision_signals: Record<string, unknown>[];
}> {
  return api.get('/scenarios/evaluate/base', { user_id: userId });
}

// Pipeline Endpoints
export async function seedScenario(params: {
  user_id: string;
  scenario_type: string;
  entry_path: string;
  name: string;
  suggested_reason?: string;
}): Promise<unknown> {
  return api.post('/scenarios/pipeline/seed', params);
}

export async function submitScenarioAnswers(
  scenarioId: string,
  answers: Record<string, unknown>
): Promise<unknown> {
  return api.post(`/scenarios/pipeline/${scenarioId}/answers`, { answers });
}

export async function getScenarioPipelineStatus(scenarioId: string): Promise<unknown> {
  return api.get(`/scenarios/pipeline/${scenarioId}/status`);
}

export async function commitScenario(scenarioId: string): Promise<unknown> {
  return api.post(`/scenarios/pipeline/${scenarioId}/commit`);
}

export async function discardScenario(scenarioId: string): Promise<unknown> {
  return api.post(`/scenarios/pipeline/${scenarioId}/discard`);
}
