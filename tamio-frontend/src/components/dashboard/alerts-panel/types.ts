/**
 * Types for Dashboard Alerts Panel
 *
 * Reuses types from alertsActions.ts where possible.
 */

import type { RiskSeverity, RiskStatus, Control } from '@/lib/api/alertsActions';

/**
 * Alert item for display in the dashboard panel
 */
export interface AlertPanelItem {
  id: string;
  section: 'requires_decision' | 'being_handled' | 'monitoring';
  alert: {
    id: string;
    title: string;
    severity: RiskSeverity;
    detected_at: string;
    deadline: string | null;
    days_until_deadline: number | null;
    due_horizon_label: string;
    cash_impact: number | null;
    buffer_impact_percent: number | null;
    impact_statement: string | null;
    primary_driver: string;
    status: RiskStatus;
  };
  recommendation: {
    controlId: string;
    name: string;
    why_it_exists: string;
  } | null;
  activeControls: Control[];
}

/**
 * Summary statistics for the alerts panel
 */
export interface AlertPanelSummary {
  requiresDecision: {
    count: number;
    totalAtRisk: number;
  };
  beingHandled: {
    count: number;
    hasExecuting: boolean;
  };
  monitoring: {
    count: number;
    totalUpcoming: number;
  };
  total: number;
}

/**
 * Return type for the useAlertsPanelData hook
 */
export interface UseAlertsPanelDataReturn {
  items: AlertPanelItem[];
  requiresDecision: AlertPanelItem[];
  beingHandled: AlertPanelItem[];
  monitoring: AlertPanelItem[];
  summary: AlertPanelSummary;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}
