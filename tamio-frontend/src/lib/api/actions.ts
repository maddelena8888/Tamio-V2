/**
 * Actions API - V4 Architecture
 *
 * API client for the Action Queue endpoints.
 */

import { api as apiClient } from "./client";

// Types
export type RiskLevel = "low" | "medium" | "high";
export type Urgency = "emergency" | "this_week" | "upcoming";
export type ActionStatus =
  | "pending_approval"
  | "approved"
  | "edited"
  | "overridden"
  | "skipped"
  | "executed"
  | "expired";

export interface ActionOption {
  id: string;
  title: string;
  description: string | null;
  risk_level: RiskLevel;
  is_recommended: boolean;
  reasoning: string[];
  risk_score: number | null;
  cash_impact: number | null;
  impact_description: string | null;
  prepared_content: Record<string, any>;
  success_probability: number | null;
  display_order: number;
}

export interface EntityLink {
  entity_type: "client" | "expense" | "obligation" | "vendor";
  entity_id: string;
  entity_name: string;
  route: string;
}

export interface ActionCard {
  id: string;
  action_type: string;
  status: ActionStatus;
  urgency: Urgency;
  problem_summary: string;
  problem_context: string | null;
  options: ActionOption[];
  created_at: string;
  deadline: string | null;
  time_remaining: string | null;
  linked_action_ids: string[];
  entity_links: EntityLink[];
}

export interface ActionQueue {
  emergency: ActionCard[];
  this_week: ActionCard[];
  upcoming: ActionCard[];
  emergency_count: number;
  this_week_count: number;
  upcoming_count: number;
  total_count: number;
}

export interface ExecutionArtifacts {
  action_type: string;
  raw_content: Record<string, any>;
  email?: {
    subject: string;
    body: string;
    recipient: string;
    copy_button?: boolean;
  };
  payment_batch?: {
    total: number;
    count: number;
    csv_available: boolean;
  };
  call?: {
    talking_points: string[];
  };
}

export interface RecentActivity {
  id: string;
  action_id: string;
  action_type: string;
  method: string;
  result: string;
  executed_at: string;
  notes: string | null;
}

// API Functions

/**
 * Get the full action queue organized by urgency.
 */
export async function getActionQueue(): Promise<ActionQueue> {
  return apiClient.get<ActionQueue>("/actions/queue");
}

/**
 * Get a single action by ID.
 */
export async function getAction(actionId: string): Promise<ActionCard> {
  return apiClient.get<ActionCard>(`/actions/${actionId}`);
}

/**
 * Approve an action with the selected option.
 */
export async function approveAction(
  actionId: string,
  optionId?: string,
  editedContent?: Record<string, any>
): Promise<ActionCard> {
  return apiClient.post<ActionCard>(`/actions/${actionId}/approve`, {
    option_id: optionId,
    edited_content: editedContent,
  });
}

/**
 * Mark an approved action as executed.
 */
export async function markExecuted(
  actionId: string,
  externalReference?: string,
  notes?: string
): Promise<{ status: string; execution_id: string }> {
  return apiClient.post(`/actions/${actionId}/execute`, {
    external_reference: externalReference,
    notes,
  });
}

/**
 * Skip an action (defer decision).
 */
export async function skipAction(
  actionId: string,
  reason?: string
): Promise<ActionCard> {
  return apiClient.post<ActionCard>(`/actions/${actionId}/skip`, {
    reason,
  });
}

/**
 * Override an action (reject recommendation, handle manually).
 */
export async function overrideAction(
  actionId: string,
  reason?: string
): Promise<ActionCard> {
  return apiClient.post<ActionCard>(`/actions/${actionId}/override`, {
    reason,
  });
}

/**
 * Get execution artifacts for an approved action.
 */
export async function getExecutionArtifacts(
  actionId: string
): Promise<ExecutionArtifacts> {
  return apiClient.get<ExecutionArtifacts>(`/actions/${actionId}/artifacts`);
}

/**
 * Get all approved actions waiting for execution.
 */
export async function getExecutionQueue(): Promise<ActionCard[]> {
  return apiClient.get<ActionCard[]>("/actions/execution/queue");
}

/**
 * Get recent execution activity.
 */
export async function getRecentActivity(
  limit: number = 20
): Promise<RecentActivity[]> {
  return apiClient.get<RecentActivity[]>(
    `/actions/execution/activity?limit=${limit}`
  );
}
