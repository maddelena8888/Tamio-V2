// ============================================================================
// Rules & Alerts Types
// ============================================================================

export type RuleType =
  | 'cash_buffer'
  | 'tax_vat_reserve'
  | 'payroll'
  | 'receivables'
  | 'unusual_activity';

export type RuleStatus = 'active' | 'paused';
export type AlertSeverity = 'warning' | 'urgent';
export type AlertFrequency = 'every_time' | 'daily_digest' | 'weekly_summary';

// ============================================================================
// Rule Type Configurations
// ============================================================================

export interface CashBufferConfig {
  threshold_type: 'fixed_amount' | 'days_of_expenses';
  threshold_amount: number;
  days_of_expenses?: number;
  look_ahead_period: '2_weeks' | '1_month' | '3_months';
  severity: AlertSeverity;
}

export interface TaxVATConfig {
  tax_type: 'vat' | 'corporation_tax' | 'custom';
  custom_name?: string;
  percentage: number;
  calculation_source: 'incoming_payments' | 'revenue';
  reserve_account?: string;
  alert_threshold_type: 'shortfall_amount' | 'days_before_due';
  alert_threshold_value: number;
  due_date_reminder_enabled: boolean;
  due_date_reminder_days?: number;
}

export interface PayrollConfig {
  payroll_amount: number;
  auto_detect_enabled: boolean;
  pay_date_type: 'day_of_month' | 'specific_dates';
  pay_day: number;
  specific_dates?: string[];
  alert_days_before: number;
  buffer_amount: number;
}

export interface ReceivablesConfig {
  overdue_days: number;
  minimum_invoice_amount: number;
  escalation_enabled: boolean;
  escalation_tiers?: {
    tier1_days: number;
    tier1_severity: 'nudge' | 'warning' | 'urgent';
    tier2_days: number;
    tier2_severity: 'nudge' | 'warning' | 'urgent';
    tier3_days: number;
    tier3_severity: 'nudge' | 'warning' | 'urgent';
  };
  customer_filter: 'all' | 'specific';
  specific_customers?: string[];
  aggregate_alert_enabled: boolean;
  aggregate_threshold?: number;
}

export interface UnusualActivityConfig {
  monitor_type: 'all_spending' | 'specific_category' | 'specific_vendor';
  specific_value?: string;
  sensitivity_preset: 'conservative' | 'moderate' | 'sensitive' | 'custom';
  custom_threshold_percent?: number;
  comparison_months: number;
  minimum_overspend_amount: number;
  alert_on_overspending: boolean;
  alert_on_unusual_income: boolean;
}

export type RuleConfig =
  | CashBufferConfig
  | TaxVATConfig
  | PayrollConfig
  | ReceivablesConfig
  | UnusualActivityConfig;

// ============================================================================
// Alert Preferences
// ============================================================================

export interface AlertPreferences {
  show_in_feed: boolean;
  send_email: boolean;
  send_slack: boolean;
  frequency: AlertFrequency;
}

// ============================================================================
// Rule Entity
// ============================================================================

export interface Rule {
  id: string;
  user_id: string;
  name: string;
  description: string;
  rule_type: RuleType;
  config: RuleConfig;
  alert_preferences: AlertPreferences;
  status: RuleStatus;
  created_at: string;
  updated_at: string;
  last_triggered_at: string | null;
  trigger_count: number;
  // Computed status for display
  current_evaluation?: {
    status: 'healthy' | 'warning' | 'triggered';
    message: string;
    data?: Record<string, unknown>;
  };
}

export interface CreateRuleInput {
  name: string;
  description?: string;
  rule_type: RuleType;
  config: RuleConfig;
  alert_preferences: AlertPreferences;
}

export interface UpdateRuleInput {
  name?: string;
  description?: string;
  config?: Partial<RuleConfig>;
  alert_preferences?: Partial<AlertPreferences>;
  status?: RuleStatus;
}

// ============================================================================
// Rule Type Metadata
// ============================================================================

export interface RuleTypeInfo {
  type: RuleType;
  title: string;
  description: string;
  icon: string;
  defaultConfig: RuleConfig;
  defaultName: string;
}

export const RULE_TYPES: RuleTypeInfo[] = [
  {
    type: 'cash_buffer',
    title: 'Cash Buffer Alert',
    description: 'Alert when projected cash falls below a safety threshold',
    icon: 'Wallet',
    defaultName: 'Cash Buffer Alert',
    defaultConfig: {
      threshold_type: 'days_of_expenses',
      threshold_amount: 50000,
      days_of_expenses: 30,
      look_ahead_period: '1_month',
      severity: 'warning',
    } as CashBufferConfig,
  },
  {
    type: 'tax_vat_reserve',
    title: 'Tax & VAT Reserve',
    description: 'Calculate tax obligations and alert when reserves are insufficient',
    icon: 'Receipt',
    defaultName: 'VAT Reserve Alert',
    defaultConfig: {
      tax_type: 'vat',
      percentage: 20,
      calculation_source: 'incoming_payments',
      alert_threshold_type: 'shortfall_amount',
      alert_threshold_value: 1000,
      due_date_reminder_enabled: true,
      due_date_reminder_days: 14,
    } as TaxVATConfig,
  },
  {
    type: 'payroll',
    title: 'Payroll Alert',
    description: 'Ensure you can always cover payroll',
    icon: 'Users',
    defaultName: 'Payroll Coverage Alert',
    defaultConfig: {
      payroll_amount: 0,
      auto_detect_enabled: false,
      pay_date_type: 'day_of_month',
      pay_day: 25,
      alert_days_before: 7,
      buffer_amount: 0,
    } as PayrollConfig,
  },
  {
    type: 'receivables',
    title: 'Receivables Alert',
    description: 'Track overdue customer payments',
    icon: 'FileText',
    defaultName: 'Overdue Receivables Alert',
    defaultConfig: {
      overdue_days: 14,
      minimum_invoice_amount: 500,
      escalation_enabled: false,
      customer_filter: 'all',
      aggregate_alert_enabled: false,
    } as ReceivablesConfig,
  },
  {
    type: 'unusual_activity',
    title: 'Unusual Activity Alert',
    description: 'Detect spending anomalies based on your sensitivity preference',
    icon: 'TrendingUp',
    defaultName: 'Unusual Spending Alert',
    defaultConfig: {
      monitor_type: 'all_spending',
      sensitivity_preset: 'moderate',
      comparison_months: 3,
      minimum_overspend_amount: 500,
      alert_on_overspending: true,
      alert_on_unusual_income: false,
    } as UnusualActivityConfig,
  },
];

export const DEFAULT_ALERT_PREFERENCES: AlertPreferences = {
  show_in_feed: true,
  send_email: true,
  send_slack: false,
  frequency: 'daily_digest',
};

// ============================================================================
// Filter Types
// ============================================================================

export type RulesFilter = 'all' | 'active' | 'triggered_today';

// ============================================================================
// localStorage Functions
// ============================================================================

const STORAGE_KEY_PREFIX = 'tamio_rules_';
const STORAGE_VERSION = 1;

interface StoredRulesData {
  version: number;
  rules: Rule[];
  lastUpdated: string;
}

export function getRulesStorageKey(userId: string): string {
  return `${STORAGE_KEY_PREFIX}${userId}`;
}

export function loadRulesFromStorage(userId: string): Rule[] {
  if (typeof window === 'undefined') return [];

  try {
    const stored = localStorage.getItem(getRulesStorageKey(userId));
    if (!stored) return [];

    const data = JSON.parse(stored) as StoredRulesData;
    if (data.version !== STORAGE_VERSION) return [];

    return data.rules;
  } catch {
    return [];
  }
}

export function saveRulesToStorage(userId: string, rules: Rule[]): void {
  if (typeof window === 'undefined') return;

  try {
    const data: StoredRulesData = {
      version: STORAGE_VERSION,
      rules,
      lastUpdated: new Date().toISOString(),
    };
    localStorage.setItem(getRulesStorageKey(userId), JSON.stringify(data));
  } catch (error) {
    console.error('Failed to save rules to storage:', error);
  }
}

export function generateRuleId(): string {
  return `rule_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// ============================================================================
// Utility Functions
// ============================================================================

export function getRuleTypeInfo(type: RuleType): RuleTypeInfo | undefined {
  return RULE_TYPES.find((rt) => rt.type === type);
}

export function generateRuleDescription(rule: Rule): string {
  const config = rule.config;

  switch (rule.rule_type) {
    case 'cash_buffer': {
      const c = config as CashBufferConfig;
      const threshold =
        c.threshold_type === 'fixed_amount'
          ? `£${c.threshold_amount.toLocaleString()}`
          : `${c.days_of_expenses} days of expenses`;
      const period =
        c.look_ahead_period === '2_weeks'
          ? '2 weeks'
          : c.look_ahead_period === '1_month'
            ? '1 month'
            : '3 months';
      return `Alert when projected cash in the next ${period} falls below ${threshold}`;
    }
    case 'tax_vat_reserve': {
      const c = config as TaxVATConfig;
      const taxName = c.tax_type === 'custom' ? c.custom_name : c.tax_type.toUpperCase();
      return `Set aside ${c.percentage}% of ${c.calculation_source === 'incoming_payments' ? 'incoming payments' : 'revenue'} for ${taxName}`;
    }
    case 'payroll': {
      const c = config as PayrollConfig;
      return `Alert ${c.alert_days_before} days before payday if projected cash won't cover £${c.payroll_amount.toLocaleString()}${c.buffer_amount > 0 ? ` plus £${c.buffer_amount.toLocaleString()} buffer` : ''}`;
    }
    case 'receivables': {
      const c = config as ReceivablesConfig;
      return `Alert when invoices over £${c.minimum_invoice_amount.toLocaleString()} are more than ${c.overdue_days} days overdue`;
    }
    case 'unusual_activity': {
      const c = config as UnusualActivityConfig;
      const thresholdPercent =
        c.sensitivity_preset === 'conservative'
          ? 50
          : c.sensitivity_preset === 'moderate'
            ? 25
            : c.sensitivity_preset === 'sensitive'
              ? 10
              : c.custom_threshold_percent || 25;
      const target =
        c.monitor_type === 'all_spending'
          ? 'any category'
          : c.monitor_type === 'specific_category'
            ? c.specific_value || 'selected category'
            : c.specific_value || 'selected vendor';
      return `Alert when spending in ${target} exceeds the ${c.comparison_months}-month average by more than ${thresholdPercent}%`;
    }
    default:
      return '';
  }
}

export function getStatusStyles(status: 'healthy' | 'warning' | 'triggered' | 'paused'): {
  bgClass: string;
  textClass: string;
  dotClass: string;
} {
  switch (status) {
    case 'healthy':
      return {
        bgClass: 'bg-lime/20',
        textClass: 'text-lime-dark',
        dotClass: 'bg-lime',
      };
    case 'warning':
      return {
        bgClass: 'bg-amber-100',
        textClass: 'text-amber-700',
        dotClass: 'bg-amber-500',
      };
    case 'triggered':
      return {
        bgClass: 'bg-tomato/20',
        textClass: 'text-tomato',
        dotClass: 'bg-tomato',
      };
    case 'paused':
      return {
        bgClass: 'bg-gray-100',
        textClass: 'text-gray-500',
        dotClass: 'bg-gray-400',
      };
  }
}
