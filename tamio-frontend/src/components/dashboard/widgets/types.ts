/**
 * Dashboard Widget Type Definitions
 */

import type { LucideIcon } from 'lucide-react';
import type { HealthMetricsResponse } from '@/lib/api/health';
import type { ForecastResponse, CashPositionResponse } from '@/lib/api/types';
import type { Risk } from '@/lib/api/alertsActions';

// ============================================================================
// Widget Identifiers
// ============================================================================

export type WidgetId =
  // Core Metrics
  | 'cash_position'
  | 'cash_runway'
  | 'health_status'
  | 'net_cash_flow'
  // Obligations
  | 'obligations_tracker'
  | 'next_big_obligation'
  | 'payroll_countdown'
  | 'vat_tax_countdown'
  | 'ap_aging'
  | 'ar_aging'
  // Monitoring
  | 'alerts_feed'
  | 'recent_transactions'
  | 'bank_accounts_overview'
  | 'data_sources_status'
  // Analysis
  | 'scenario_comparison'
  | 'weekly_cash_pattern'
  | 'customer_payment_health'
  | 'supplier_payment_schedule';

export type WidgetCategory = 'core_metrics' | 'obligations' | 'monitoring' | 'analysis';

// ============================================================================
// View Presets
// ============================================================================

export type ViewPreset = 'leader' | 'finance_manager' | 'custom';

// ============================================================================
// Widget Configuration
// ============================================================================

export interface WidgetConfig {
  /** Unique instance ID (e.g., "cash_runway_1") */
  id: string;
  /** Widget type from registry */
  widgetId: WidgetId;
  /** Widget-specific settings */
  settings: Record<string, unknown>;
}

// ============================================================================
// Widget Definition (Registry Entry)
// ============================================================================

export interface WidgetDefinition {
  id: WidgetId;
  name: string;
  description: string;
  category: WidgetCategory;
  icon: LucideIcon;
  defaultSettings: Record<string, unknown>;
  component: React.ComponentType<WidgetProps>;
}

// ============================================================================
// Widget Component Props
// ============================================================================

export interface WidgetProps {
  /** Unique instance ID */
  instanceId: string;
  /** Widget-specific settings */
  settings: Record<string, unknown>;
  /** Optional className for styling */
  className?: string;
}

// ============================================================================
// Widget Data (provided via context)
// ============================================================================

export interface WidgetData {
  healthData: HealthMetricsResponse | null;
  forecastData: ForecastResponse | null;
  risksData: Risk[] | null;
  cashPosition: CashPositionResponse | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

// ============================================================================
// Dashboard State
// ============================================================================

export interface DashboardState {
  /** Schema version for migrations */
  version: number;
  /** Current view preset */
  viewPreset: ViewPreset;
  /** Active widget instances */
  widgets: WidgetConfig[];
  /** Last modification timestamp */
  lastModified: string;
}

// ============================================================================
// Category Metadata
// ============================================================================

export interface CategoryDefinition {
  label: string;
  description: string;
  widgets: WidgetId[];
}
