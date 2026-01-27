/**
 * Alerts & Actions API - V4 Risk/Controls Architecture
 *
 * API client for the refactored Alerts & Actions page.
 * Provides endpoints for:
 * - Risk retrieval with computed labels
 * - Control management with state transitions
 * - Cross-linking between risks and controls
 */

import { api as apiClient } from './client';

// ============================================================================
// Types
// ============================================================================

export type RiskSeverity = 'urgent' | 'high' | 'normal';
export type RiskStatus = 'active' | 'acknowledged' | 'preparing' | 'resolved' | 'dismissed';
export type ControlState = 'pending' | 'active' | 'completed' | 'needs_review';
export type ActionType = 'email' | 'payment_batch' | 'transfer' | 'manual' | 'invoice_follow_up' | 'vendor_delay' | 'payroll_contingency';
export type ActionStepOwner = 'tamio' | 'user';
export type ActionStepStatus = 'pending' | 'in_progress' | 'completed' | 'skipped';

/**
 * Individual step within a control workflow
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
 * Risk entity - represents a detected cash flow risk
 * Maps from backend DetectionAlert
 */
export interface Risk {
  id: string;
  title: string;
  severity: RiskSeverity;
  detected_at: string;

  // Due horizon
  deadline: string | null;
  days_until_deadline: number | null;
  due_horizon_label: string; // "Due today", "Due Friday", "In 5 days"

  // Impact
  cash_impact: number | null;
  buffer_impact_percent: number | null;
  impact_statement: string | null; // e.g., "If unpaid, cash drops to $142K in Week 3 — $58K below buffer"

  // Driver
  primary_driver: string; // e.g., "RetailCo payment 14d overdue"
  detection_type: string;

  // Context
  context_bullets: string[];
  context_data: Record<string, unknown>;

  // Linked controls
  linked_control_ids: string[];

  // Status
  status: RiskStatus;
}

/**
 * Suggested control that was rejected - shown for auditability
 */
export interface RejectedSuggestion {
  id: string;
  title: string;
  rejected_at: string;
  reason?: string;
}

/**
 * Control entity - represents an active intervention
 * Maps from backend PreparedAction
 */
export interface Control {
  id: string;
  name: string;

  // State (replaces kanban columns)
  state: ControlState;
  state_label: string; // "Pending", "In progress", "Completed", "Needs review"

  // Linked risks
  linked_risk_ids: string[];

  // What/Why
  action_type: ActionType;
  why_it_exists: string; // Generated explanation

  // Responsibility split
  tamio_handles: string[]; // e.g., ["Draft email", "Calculate timing"]
  user_handles: string[]; // e.g., ["Review and send", "Confirm receipt"]

  // Steps
  action_steps: ActionStep[];

  // Timing
  deadline: string | null;
  created_at: string;
  approved_at: string | null;
  completed_at: string | null;

  // Content
  draft_content: Record<string, unknown>;
  impact_amount: number | null;

  // For auditability
  rejected_suggestions?: RejectedSuggestion[];
}

/**
 * Response from risks endpoint
 */
export interface RisksResponse {
  risks: Risk[];
  total_count: number;
}

/**
 * Response from controls endpoint
 */
export interface ControlsResponse {
  controls: Control[];
  total_count: number;
}

/**
 * State transition request
 */
export interface UpdateControlStateRequest {
  state: ControlState;
  notes?: string;
}

/**
 * Filter options for risks
 */
export interface RiskFilters {
  severity?: RiskSeverity | 'all';
  timing?: 'today' | 'this_week' | 'next_two_weeks' | 'all';
  status?: RiskStatus | 'all';
  category?: 'obligations' | 'receivables';
}

/**
 * Filter options for controls
 */
export interface ControlFilters {
  state?: ControlState | 'all';
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get all active risks with computed labels.
 * Returns risks ordered by severity and deadline.
 */
export async function getRisks(filters?: RiskFilters): Promise<RisksResponse> {
  const params = new URLSearchParams();
  if (filters?.severity && filters.severity !== 'all') {
    params.append('severity', filters.severity);
  }
  if (filters?.timing && filters.timing !== 'all') {
    params.append('timing', filters.timing);
  }
  if (filters?.status && filters.status !== 'all') {
    params.append('status', filters.status);
  }
  if (filters?.category) {
    params.append('category', filters.category);
  }

  const queryString = params.toString();
  const url = `/alerts-actions/risks${queryString ? `?${queryString}` : ''}`;
  return apiClient.get<RisksResponse>(url);
}

/**
 * Get a single risk by ID with full details.
 */
export async function getRisk(riskId: string): Promise<Risk> {
  return apiClient.get<Risk>(`/alerts-actions/risks/${riskId}`);
}

/**
 * Dismiss a risk.
 */
export async function dismissRisk(riskId: string): Promise<{ success: boolean }> {
  return apiClient.post(`/alerts-actions/risks/${riskId}/dismiss`, {});
}

/**
 * Acknowledge a risk (mark as seen).
 */
export async function acknowledgeRisk(riskId: string): Promise<{ success: boolean }> {
  return apiClient.post(`/alerts-actions/risks/${riskId}/acknowledge`, {});
}

/**
 * Get all active controls with state information.
 */
export async function getControls(filters?: ControlFilters): Promise<ControlsResponse> {
  const params = new URLSearchParams();
  if (filters?.state && filters.state !== 'all') {
    params.append('state', filters.state);
  }

  const queryString = params.toString();
  const url = `/alerts-actions/controls${queryString ? `?${queryString}` : ''}`;
  return apiClient.get<ControlsResponse>(url);
}

/**
 * Get a single control by ID with full details.
 */
export async function getControl(controlId: string): Promise<Control> {
  return apiClient.get<Control>(`/alerts-actions/controls/${controlId}`);
}

/**
 * Update a control's state.
 * Allows transitions including Completed -> Active (bug fix).
 */
export async function updateControlState(
  controlId: string,
  request: UpdateControlStateRequest
): Promise<{ success: boolean; control: Control }> {
  return apiClient.patch(`/alerts-actions/controls/${controlId}/state`, request);
}

/**
 * Approve a suggested control (from a risk's suggestions).
 */
export async function approveControl(
  controlId: string,
  optionId?: string
): Promise<{ success: boolean; control: Control }> {
  return apiClient.post(`/alerts-actions/controls/${controlId}/approve`, {
    option_id: optionId,
  });
}

/**
 * Reject a suggested control.
 */
export async function rejectControl(
  controlId: string,
  reason?: string
): Promise<{ success: boolean }> {
  return apiClient.post(`/alerts-actions/controls/${controlId}/reject`, {
    reason,
  });
}

/**
 * Mark a control as completed.
 */
export async function completeControl(
  controlId: string,
  externalReference?: string,
  notes?: string
): Promise<{ success: boolean }> {
  return apiClient.post(`/alerts-actions/controls/${controlId}/complete`, {
    external_reference: externalReference,
    notes,
  });
}

/**
 * Get controls linked to a specific risk.
 */
export async function getControlsForRisk(riskId: string): Promise<Control[]> {
  const response = await apiClient.get<{ controls: Control[] }>(
    `/alerts-actions/risks/${riskId}/controls`
  );
  return response.controls;
}

/**
 * Get risks linked to a specific control.
 */
export async function getRisksForControl(controlId: string): Promise<Risk[]> {
  const response = await apiClient.get<{ risks: Risk[] }>(
    `/alerts-actions/controls/${controlId}/risks`
  );
  return response.risks;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Map backend severity to frontend display values
 */
export function mapSeverity(backendSeverity: string): RiskSeverity {
  const mapping: Record<string, RiskSeverity> = {
    emergency: 'urgent',
    this_week: 'high',
    upcoming: 'normal',
    // Also handle direct mappings
    urgent: 'urgent',
    high: 'high',
    normal: 'normal',
  };
  return mapping[backendSeverity] || 'normal';
}

/**
 * Map backend status to frontend control state
 */
export function mapControlState(backendStatus: string): ControlState {
  const mapping: Record<string, ControlState> = {
    pending_approval: 'pending',
    approved: 'active',
    edited: 'active',
    executed: 'completed',
    overridden: 'needs_review',
    skipped: 'needs_review',
    expired: 'needs_review',
  };
  return mapping[backendStatus] || 'pending';
}

/**
 * Get display label for control state
 */
export function getControlStateLabel(state: ControlState): string {
  const labels: Record<ControlState, string> = {
    pending: 'Pending',
    active: 'In progress',
    completed: 'Completed',
    needs_review: 'Needs review',
  };
  return labels[state];
}

/**
 * Get color classes for severity badge
 */
export function getSeverityStyles(severity: RiskSeverity): {
  bgClass: string;
  textClass: string;
  borderClass: string;
} {
  const styles: Record<RiskSeverity, { bgClass: string; textClass: string; borderClass: string }> = {
    urgent: {
      bgClass: 'bg-tomato/10',
      textClass: 'text-tomato',
      borderClass: 'border-tomato/30',
    },
    high: {
      bgClass: 'bg-yellow-500/10',
      textClass: 'text-yellow-700',
      borderClass: 'border-yellow-500/30',
    },
    normal: {
      bgClass: 'bg-lime/10',
      textClass: 'text-lime-700',
      borderClass: 'border-lime/30',
    },
  };
  return styles[severity];
}

/**
 * Get color classes for control state
 */
export function getControlStateStyles(state: ControlState): {
  dotClass: string;
  bgClass: string;
  textClass: string;
} {
  const styles: Record<ControlState, { dotClass: string; bgClass: string; textClass: string }> = {
    pending: {
      dotClass: 'bg-gray-400',
      bgClass: 'bg-gray-50',
      textClass: 'text-gray-600',
    },
    active: {
      dotClass: 'bg-blue-500',
      bgClass: 'bg-blue-50',
      textClass: 'text-blue-700',
    },
    completed: {
      dotClass: 'bg-green-500',
      bgClass: 'bg-green-50',
      textClass: 'text-green-700',
    },
    needs_review: {
      dotClass: 'bg-amber-500',
      bgClass: 'bg-amber-50',
      textClass: 'text-amber-700',
    },
  };
  return styles[state];
}

// ============================================================================
// Decision Queue Types
// ============================================================================

export type DecisionQueueSection = 'requires_decision' | 'being_handled' | 'monitoring';

/**
 * Alert data extracted from Risk for display in DecisionCard
 */
export interface AlertData {
  id: string;
  title: string;
  severity: RiskSeverity;
  detected_at: string;
  deadline: string | null;
  due_horizon_label: string;
  cash_impact: number | null;
  buffer_impact_percent: number | null;
  impact_statement: string | null; // Quantified risk statement
  primary_driver: string;
  context_bullets: string[];
  status: RiskStatus;
}

/**
 * Recommendation data from a pending Control
 */
export interface RecommendationData {
  controlId: string;
  name: string;
  why_it_exists: string;
  tamio_handles: string[];
  user_handles: string[];
  impact_amount: number | null;
  expected_outcome?: string;
}

/**
 * Combined decision item that pairs an alert with its recommendation
 */
export interface DecisionItem {
  id: string;
  section: DecisionQueueSection;
  alert: AlertData;
  recommendation: RecommendationData | null;
  activeControls: Control[];
  forecastDaysAgo?: number;
}

/**
 * Summary statistics for the decision queue
 */
export interface DecisionQueueSummary {
  requires_decision: {
    count: number;
    total_at_risk: number;
  };
  being_handled: {
    count: number;
    has_executing: boolean;
  };
  monitoring: {
    count: number;
    total_upcoming: number;
  };
}

// ============================================================================
// Home Page Alert Functions
// ============================================================================

/**
 * Get the highest priority alert for the home page hero.
 * Returns the most urgent active risk, or null if none exist.
 */
export async function getHighestPriorityAlert(): Promise<Risk | null> {
  const response = await getRisks({ status: 'active' });

  if (!response.risks.length) return null;

  const severityOrder: Record<RiskSeverity, number> = {
    urgent: 0,
    high: 1,
    normal: 2,
  };

  return response.risks.sort((a, b) => {
    const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
    if (severityDiff !== 0) return severityDiff;
    // Secondary sort by cash impact (higher first)
    return (b.cash_impact || 0) - (a.cash_impact || 0);
  })[0];
}
