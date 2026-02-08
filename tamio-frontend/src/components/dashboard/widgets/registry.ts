/**
 * Widget Registry - Metadata and factory for all dashboard widgets
 *
 * Defines:
 * - All available widgets with their metadata
 * - Preset configurations for Leader and Finance Manager views
 * - Category organization for the widget library
 */

import {
  TrendingUp,
  Activity,
  AlertCircle,
  DollarSign,
  Calendar,
  CreditCard,
  Building2,
  ArrowUpDown,
} from 'lucide-react';
import type { WidgetId, WidgetDefinition, CategoryDefinition, ViewPreset } from './types';

// Import widget components (lazy loaded for code splitting)
import { CashRunwayWidget } from './CashRunwayWidget';
import { HealthStatusWidget } from './HealthStatusWidget';
import { NextBigObligationWidget } from './NextBigObligationWidget';
import { CashPositionWidget } from './CashPositionWidget';
import { ObligationsTrackerWidget } from './ObligationsTrackerWidget';
import { AlertsFeedWidget } from './AlertsFeedWidget';
import { NetCashFlowWidget } from './NetCashFlowWidget';
import { BankAccountsOverviewWidget } from './BankAccountsOverviewWidget';

// ============================================================================
// Preset Configurations
// ============================================================================

/**
 * Preset view configurations mapping to their widget IDs
 */
export const PRESET_CONFIGS: Record<Exclude<ViewPreset, 'custom'>, WidgetId[]> = {
  leader: ['cash_runway', 'health_status', 'next_big_obligation'],
  finance_manager: [
    'cash_position',
    'cash_runway',
    'obligations_tracker',
    'alerts_feed',
    'net_cash_flow',
    'bank_accounts_overview',
  ],
};

// ============================================================================
// Widget Registry
// ============================================================================

/**
 * Complete registry of all available widgets
 */
export const WIDGET_REGISTRY: Partial<Record<WidgetId, WidgetDefinition>> = {
  // Core Metrics
  cash_position: {
    id: 'cash_position',
    name: 'Cash Position',
    description: 'Current total cash across all accounts with trend',
    category: 'core_metrics',
    icon: DollarSign,
    defaultSettings: { showTrend: true },
    component: CashPositionWidget,
  },
  cash_runway: {
    id: 'cash_runway',
    name: 'Cash Runway',
    description: 'Weeks of operation remaining at current burn rate',
    category: 'core_metrics',
    icon: TrendingUp,
    defaultSettings: { showSparkline: true },
    component: CashRunwayWidget,
  },
  health_status: {
    id: 'health_status',
    name: 'Health Status',
    description: 'Overall health assessment with key status indicator',
    category: 'core_metrics',
    icon: Activity,
    defaultSettings: {},
    component: HealthStatusWidget,
  },
  net_cash_flow: {
    id: 'net_cash_flow',
    name: 'Net Cash Flow',
    description: 'Money in vs money out comparison',
    category: 'core_metrics',
    icon: ArrowUpDown,
    defaultSettings: { period: 'month' },
    component: NetCashFlowWidget,
  },

  // Obligations
  obligations_tracker: {
    id: 'obligations_tracker',
    name: 'Obligations Tracker',
    description: 'Upcoming payments over the next 30 days',
    category: 'obligations',
    icon: Calendar,
    defaultSettings: { daysAhead: 30 },
    component: ObligationsTrackerWidget,
  },
  next_big_obligation: {
    id: 'next_big_obligation',
    name: 'Next Big Obligation',
    description: 'Your largest upcoming payment highlighted',
    category: 'obligations',
    icon: CreditCard,
    defaultSettings: {},
    component: NextBigObligationWidget,
  },

  // Monitoring
  alerts_feed: {
    id: 'alerts_feed',
    name: 'Alerts & Actions',
    description: 'Critical alerts requiring your attention',
    category: 'monitoring',
    icon: AlertCircle,
    defaultSettings: { maxItems: 5 },
    component: AlertsFeedWidget,
  },
  bank_accounts_overview: {
    id: 'bank_accounts_overview',
    name: 'Bank Accounts',
    description: 'Connected accounts with balances and sync status',
    category: 'monitoring',
    icon: Building2,
    defaultSettings: {},
    component: BankAccountsOverviewWidget,
  },
};

// ============================================================================
// Category Definitions
// ============================================================================

/**
 * Widget categories for organizing the widget library
 */
export const WIDGET_CATEGORIES: Record<string, CategoryDefinition> = {
  core_metrics: {
    label: 'Core Metrics',
    description: 'Key financial health indicators',
    widgets: ['cash_position', 'cash_runway', 'health_status', 'net_cash_flow'],
  },
  obligations: {
    label: 'Obligations',
    description: 'Track what you owe and when',
    widgets: [
      'obligations_tracker',
      'next_big_obligation',
      'payroll_countdown',
      'vat_tax_countdown',
      'ap_aging',
      'ar_aging',
    ],
  },
  monitoring: {
    label: 'Monitoring',
    description: 'Real-time status and alerts',
    widgets: ['alerts_feed', 'recent_transactions', 'bank_accounts_overview', 'data_sources_status'],
  },
  analysis: {
    label: 'Analysis',
    description: 'Patterns and comparisons',
    widgets: [
      'scenario_comparison',
      'weekly_cash_pattern',
      'customer_payment_health',
      'supplier_payment_schedule',
    ],
  },
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get widget definition by ID
 */
export function getWidgetDefinition(widgetId: WidgetId): WidgetDefinition | undefined {
  return WIDGET_REGISTRY[widgetId];
}

/**
 * Get all implemented widgets (those with components)
 */
export function getImplementedWidgets(): WidgetDefinition[] {
  return Object.values(WIDGET_REGISTRY).filter(
    (def): def is WidgetDefinition => def !== undefined && def.component !== undefined
  );
}

/**
 * Get implemented widgets by category
 */
export function getWidgetsByCategory(category: string): WidgetDefinition[] {
  return getImplementedWidgets().filter((def) => def.category === category);
}

/**
 * Check if a widget is implemented
 */
export function isWidgetImplemented(widgetId: WidgetId): boolean {
  return WIDGET_REGISTRY[widgetId]?.component !== undefined;
}

/**
 * Get preset display name
 */
export function getPresetDisplayName(preset: ViewPreset): string {
  const names: Record<ViewPreset, string> = {
    leader: 'Leader View',
    finance_manager: 'Finance Manager',
    custom: 'Custom',
  };
  return names[preset];
}
