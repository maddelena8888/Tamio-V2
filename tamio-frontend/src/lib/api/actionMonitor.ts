/**
 * Action Monitor API - V4 Architecture
 *
 * API client for the Action Monitor endpoints.
 * Handles problems detection, action approval/rejection, and execution tracking.
 * Now includes kanban-style action management with status updates.
 */

import { api as apiClient } from './client';

// ============================================================================
// Types
// ============================================================================

export type Severity = 'urgent' | 'high' | 'normal';
export type RiskLevel = 'low' | 'medium' | 'high';
export type ActionOptionStatus = 'pending' | 'approved' | 'rejected';
export type ActionType = 'email' | 'payment_batch' | 'transfer' | 'manual';
export type KanbanStatus = 'queued' | 'executing' | 'completed';
export type ActionStepOwner = 'tamio' | 'user';
export type ActionStepStatus = 'pending' | 'in_progress' | 'completed' | 'skipped';

/**
 * Individual step within an action workflow
 */
export interface ActionStep {
  id: string;
  title: string;
  owner: ActionStepOwner;
  status: ActionStepStatus;
  order: number;
  description?: string;
}

/**
 * Linked detection alert information
 */
export interface LinkedAlert {
  id: string;
  title: string;
  severity: Severity;
  detected_at: string;
  cash_impact: number | null;
  context_summary: string[];
}

/**
 * Action option within a problem - represents one possible response
 */
export interface ActionOption {
  id: string;
  title: string;
  description: string | null;
  risk_level: RiskLevel;
  is_recommended: boolean;
  reasoning: string[];
  cash_impact: number | null;
  impact_description: string | null;
  prepared_content: Record<string, any>;
  status: ActionOptionStatus;
  success_probability: number | null;
}

/**
 * Problem detected by background agents
 */
export interface Problem {
  id: string;
  title: string;
  severity: Severity;
  detected_at: string;
  trigger: string;
  context: string[];
  actions: ActionOption[];
}

/**
 * Prepared action ready for execution (approved action or recurring task)
 * Extended with kanban status for column management
 */
export interface PreparedAction {
  id: string;
  title: string;
  action_type: ActionType;
  urgency: Severity;
  impact_amount: number | null;
  deadline: string | null;
  problem_context: string | null;
  is_recurring: boolean;
  draft_content: Record<string, any>;
  // Kanban-specific fields
  status: KanbanStatus;
  linked_entity_type?: 'client' | 'expense_bucket';
  linked_entity_id?: string;
  linked_entity_name?: string;
  detection_id?: string;
  is_system_generated: boolean;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  notes?: string;
  // V4 additions: workflow steps and linked alert
  action_steps?: ActionStep[];
  linked_alert?: LinkedAlert;
  approved_at?: string;
}

/**
 * Response from problems endpoint
 */
export interface ProblemsResponse {
  problems: Problem[];
}

/**
 * Response from actions endpoint (grouped by status)
 */
export interface ActionsResponse {
  queued: PreparedAction[];
  executing: PreparedAction[];
  completed: PreparedAction[];
}

/**
 * Response from outstanding actions endpoint (legacy)
 */
export interface OutstandingActionsResponse {
  actions: PreparedAction[];
}

/**
 * Create manual action request
 */
export interface CreateActionRequest {
  title: string;
  action_type: ActionType;
  priority: Severity;
  due_date: string;
  linked_entity_type?: 'client' | 'expense_bucket';
  linked_entity_id?: string;
  impact_amount?: number;
  notes?: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get problems with pending actions for review.
 * Returns problems ordered by severity (urgent -> high -> normal).
 */
export async function getProblemsToReview(): Promise<Problem[]> {
  const response = await apiClient.get<ProblemsResponse>('/action-monitor/problems');
  return response.problems;
}

/**
 * Get all actions grouped by status (queued, executing, completed).
 * Used for the kanban board view.
 */
export async function getActions(): Promise<ActionsResponse> {
  return apiClient.get<ActionsResponse>('/action-monitor/actions');
}

/**
 * Get outstanding actions (approved + recurring).
 * Returns actions ready for execution.
 * @deprecated Use getActions() for kanban view
 */
export async function getOutstandingActions(): Promise<PreparedAction[]> {
  const response = await apiClient.get<OutstandingActionsResponse>('/action-monitor/outstanding');
  return response.actions;
}

/**
 * Create a manual action.
 * Adds the action to the Queued column.
 */
export async function createAction(data: CreateActionRequest): Promise<{ success: boolean; action: PreparedAction }> {
  return apiClient.post('/action-monitor/actions', data);
}

/**
 * Update action status (for drag-and-drop).
 * Moves action between kanban columns.
 */
export async function updateActionStatus(
  actionId: string,
  status: KanbanStatus
): Promise<{ success: boolean; action: PreparedAction }> {
  return apiClient.patch(`/api/action-monitor/actions/${actionId}/status`, { status });
}

/**
 * Approve an action option.
 * Moves the action to Outstanding Actions queue.
 */
export async function approveActionOption(actionId: string): Promise<{ success: boolean; action: ActionOption }> {
  return apiClient.post(`/api/action-monitor/actions/${actionId}/approve`, {});
}

/**
 * Reject an action option.
 * Marks the action as rejected.
 */
export async function rejectActionOption(actionId: string): Promise<{ success: boolean }> {
  return apiClient.post(`/api/action-monitor/actions/${actionId}/reject`, {});
}

/**
 * Dismiss a problem entirely.
 * Removes the problem from the review queue.
 */
export async function dismissProblem(problemId: string): Promise<{ success: boolean }> {
  return apiClient.post(`/api/action-monitor/problems/${problemId}/dismiss`, {});
}

/**
 * Mark an outstanding action as completed.
 * Moves the action to the Completed column.
 */
export async function markActionComplete(
  actionId: string,
  externalReference?: string,
  notes?: string
): Promise<{ success: boolean }> {
  return apiClient.post(`/api/action-monitor/actions/${actionId}/complete`, {
    external_reference: externalReference,
    notes,
  });
}

/**
 * Archive all completed actions.
 * Removes completed actions from the board.
 */
export async function archiveCompletedActions(): Promise<{ success: boolean; archived_count: number }> {
  return apiClient.post('/action-monitor/actions/archive-completed', {});
}

/**
 * Get execution artifacts for an action (email draft, CSV, etc.)
 */
export async function getActionArtifacts(actionId: string): Promise<{
  action_type: ActionType;
  content: Record<string, any>;
  download_url?: string;
}> {
  return apiClient.get(`/api/action-monitor/actions/${actionId}/artifacts`);
}

// ============================================================================
// Action Queue API (for consistent counts)
// ============================================================================

/**
 * Response from action queue endpoint with counts
 */
export interface ActionQueueResponse {
  emergency: PreparedAction[];
  this_week: PreparedAction[];
  upcoming: PreparedAction[];
  emergency_count: number;
  this_week_count: number;
  upcoming_count: number;
  total_count: number;
}

/**
 * Get action queue with counts organized by urgency.
 * Used as single source of truth for alert/action counts across pages.
 */
export async function getActionQueueCounts(): Promise<ActionQueueResponse> {
  return apiClient.get<ActionQueueResponse>('/actions/queue');
}

/**
 * Get approved actions in the execution queue.
 * Returns actions that have been approved and are ready for execution.
 */
export async function getExecutionQueue(): Promise<PreparedAction[]> {
  return apiClient.get<PreparedAction[]>('/actions/execution/queue');
}

// ============================================================================
// Agent Activity API
// ============================================================================

/**
 * Agent activity statistics for the homepage
 */
export interface AgentActivityStats {
  simulations_run: number;
  invoices_scanned: number;
  forecasts_updated: number;
  active_agents: number;
}

/**
 * Get aggregated agent activity stats.
 * @param hours Number of hours to look back (default: 24)
 */
export async function getAgentActivity(hours: number = 24): Promise<AgentActivityStats> {
  return apiClient.get<AgentActivityStats>(`/actions/agent-activity?hours=${hours}`);
}
