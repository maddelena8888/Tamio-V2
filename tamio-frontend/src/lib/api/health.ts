/**
 * Health Metrics API - Financial Wellness Dashboard
 *
 * API client for the Health page showing financial wellness metrics.
 */

import { api as apiClient } from './client';
import type { Risk } from './alertsActions';

// ============================================================================
// Types
// ============================================================================

export type HealthStatus = 'good' | 'warning' | 'critical';

// Obligations status: indicates coverage for upcoming obligations
export type ObligationsStatus = 'covered' | 'tight' | 'at_risk';

// Receivables status: indicates health of accounts receivable
export type ReceivablesStatus = 'healthy' | 'watch' | 'urgent';

/**
 * Data for a single health ring visualization
 */
export interface HealthRingData {
  value: number;
  percentage: number;
  status: HealthStatus;
  label: string;
  sublabel: string;
}

/**
 * Data for the Obligations Health monitor card.
 * Shows if upcoming financial obligations can be covered with available cash.
 */
export interface ObligationsHealthData {
  // Status indicator
  status: ObligationsStatus;

  // Primary metric: "X of Y due"
  covered_count: number;
  total_count: number;

  // Next obligation details
  next_obligation_name: string | null;
  next_obligation_amount: number | null;
  next_obligation_amount_formatted: string | null;
  next_obligation_days: number | null;

  // Calculated values for reference
  buffer_percentage: number;
  total_obligations: number;
  available_funds: number;
}

/**
 * Data for the Receivables Health monitor card.
 * Shows health of money owed - focusing on overdue invoices.
 */
export interface ReceivablesHealthData {
  // Status indicator
  status: ReceivablesStatus;

  // Primary metric: overdue amount
  overdue_amount: number;
  overdue_amount_formatted: string;

  // Detail line: invoice counts and lateness
  overdue_count: number;
  total_outstanding_count: number;
  avg_days_late: number;

  // Calculated values for reference
  overdue_percentage: number;
  total_outstanding_amount: number;
}

/**
 * Complete response from health metrics endpoint
 */
export interface HealthMetricsResponse {
  // Health rings
  runway: HealthRingData;          // Weeks of operation remaining
  liquidity: HealthRingData;       // Working capital ratio
  cash_velocity: HealthRingData;   // Cash conversion cycle in days

  // Monitor cards
  obligations_health: ObligationsHealthData;  // Forward-looking: Can you cover upcoming payments?
  receivables_health: ReceivablesHealthData;  // Current state: Is money owed coming in on time?

  // Critical alerts (top 3)
  critical_alerts: Risk[];

  // Metadata
  last_updated: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get all health metrics for the financial wellness dashboard.
 */
export async function getHealthMetrics(): Promise<HealthMetricsResponse> {
  return apiClient.get<HealthMetricsResponse>('/health/metrics');
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get color classes for health status
 */
export function getHealthStatusStyles(status: HealthStatus): {
  ringColor: string;
  textColor: string;
  bgColor: string;
} {
  const styles: Record<HealthStatus, { ringColor: string; textColor: string; bgColor: string }> = {
    good: {
      ringColor: 'stroke-lime',
      textColor: 'text-lime-700',
      bgColor: 'bg-lime/10',
    },
    warning: {
      ringColor: 'stroke-amber-400',
      textColor: 'text-amber-600',
      bgColor: 'bg-amber-50',
    },
    critical: {
      ringColor: 'stroke-tomato',
      textColor: 'text-tomato',
      bgColor: 'bg-tomato/10',
    },
  };
  return styles[status];
}

/**
 * Get color classes for monitor status badge
 */
export function getMonitorStatusStyles(status: MonitorStatus): {
  bgClass: string;
  textClass: string;
  icon: string;
} {
  const styles: Record<MonitorStatus, { bgClass: string; textClass: string; icon: string }> = {
    healthy: {
      bgClass: 'bg-lime/20',
      textClass: 'text-lime-700',
      icon: 'check',
    },
    watch: {
      bgClass: 'bg-amber-100',
      textClass: 'text-amber-700',
      icon: 'alert-triangle',
    },
  };
  return styles[status];
}

/**
 * Format a large number in compact form
 */
export function formatCompactAmount(amount: number): string {
  const absAmount = Math.abs(amount);
  if (absAmount >= 1_000_000) {
    return `$${(absAmount / 1_000_000).toFixed(1)}M`.replace('.0M', 'M');
  } else if (absAmount >= 1_000) {
    return `$${Math.round(absAmount / 1_000)}K`;
  }
  return `$${Math.round(absAmount)}`;
}

/**
 * Format trend with sign
 */
export function formatTrend(trend: number): string {
  const sign = trend >= 0 ? '+' : '';
  return `${sign}${trend.toFixed(1)}%`;
}

/**
 * Get styling for obligations status badge
 */
export function getObligationsStatusStyles(status: ObligationsStatus): {
  bgClass: string;
  textClass: string;
  label: string;
  icon: 'check' | 'alert-triangle' | 'alert-circle';
} {
  const styles: Record<ObligationsStatus, ReturnType<typeof getObligationsStatusStyles>> = {
    covered: {
      bgClass: 'bg-lime/20',
      textClass: 'text-lime-700',
      label: 'COVERED',
      icon: 'check',
    },
    tight: {
      bgClass: 'bg-mimi-pink/30',
      textClass: 'text-amber-700',
      label: 'TIGHT',
      icon: 'alert-triangle',
    },
    at_risk: {
      bgClass: 'bg-tomato/20',
      textClass: 'text-tomato',
      label: 'AT RISK',
      icon: 'alert-circle',
    },
  };
  return styles[status];
}

/**
 * Get styling for receivables status badge
 */
export function getReceivablesStatusStyles(status: ReceivablesStatus): {
  bgClass: string;
  textClass: string;
  label: string;
  icon: 'check' | 'alert-triangle' | 'alert-circle';
} {
  const styles: Record<ReceivablesStatus, ReturnType<typeof getReceivablesStatusStyles>> = {
    healthy: {
      bgClass: 'bg-lime/20',
      textClass: 'text-lime-700',
      label: 'HEALTHY',
      icon: 'check',
    },
    watch: {
      bgClass: 'bg-mimi-pink/30',
      textClass: 'text-amber-700',
      label: 'WATCH',
      icon: 'alert-triangle',
    },
    urgent: {
      bgClass: 'bg-tomato/20',
      textClass: 'text-tomato',
      label: 'URGENT',
      icon: 'alert-circle',
    },
  };
  return styles[status];
}
