// ============================================================================
// API Response Types for Tamio Backend
// ============================================================================

// Base Types
export type Currency = 'USD' | 'EUR' | 'GBP' | 'AUD' | 'CAD';
export type ClientType = 'retainer' | 'project' | 'usage' | 'mixed';
export type ClientStatus = 'active' | 'paused' | 'deleted';
export type PaymentBehavior = 'on_time' | 'delayed' | 'unknown';
export type RiskLevel = 'low' | 'medium' | 'high';
export type Priority = 'high' | 'medium' | 'low' | 'essential' | 'important' | 'discretionary';
export type ExpenseCategory = 'payroll' | 'rent' | 'contractors' | 'software' | 'marketing' | 'other';
export type BucketType = 'fixed' | 'variable';
export type Frequency = 'one_time' | 'weekly' | 'bi_weekly' | 'monthly' | 'quarterly' | 'annually';
export type Direction = 'in' | 'out';
export type Confidence = 'high' | 'medium' | 'low';

// Auth Types
export interface User {
  id: string;
  email: string;
  company_name?: string;
  base_currency: Currency;
  has_completed_onboarding: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  email: string;
  password: string;
}

// Cash Account Types
export interface CashAccount {
  id: string;
  user_id: string;
  account_name: string;
  balance: string;
  currency: Currency;
  as_of_date: string;
  created_at: string;
  updated_at: string | null;
}

export interface CashPositionResponse {
  accounts: CashAccount[];
  total_starting_cash: string;
}

export interface CashAccountInput {
  account_name: string;
  balance: string;
  currency: Currency;
  as_of_date: string;
}

// Client Types
export interface BillingConfig {
  amount?: string;
  frequency?: Frequency;
  day_of_month?: number;
  payment_terms?: string;
  milestones?: Array<{
    name: string;
    amount: string;
    expected_date: string;
    trigger_type: 'date_based' | 'delivery_based';
  }>;
}

// Sync-related types
export type SyncSource = 'manual' | 'xero' | 'quickbooks';
export type SyncStatus = 'synced' | 'pending_push' | 'pending_pull' | 'conflict' | 'error';

export interface Client {
  id: string;
  user_id: string;
  name: string;
  client_type: ClientType;
  currency: Currency;
  status: ClientStatus;
  payment_behavior: PaymentBehavior;
  churn_risk: RiskLevel;
  scope_risk: RiskLevel;
  billing_config: BillingConfig;
  notes: string | null;
  // Sync fields
  source: SyncSource;
  xero_contact_id: string | null;
  xero_repeating_invoice_id: string | null;
  quickbooks_customer_id: string | null;
  sync_status: SyncStatus | null;
  last_synced_at: string | null;
  sync_error: string | null;
  locked_fields: string[];
  created_at: string;
  updated_at: string | null;
}

export interface ClientCreate {
  user_id: string;
  name: string;
  client_type: ClientType;
  currency: Currency;
  status: ClientStatus;
  payment_behavior?: PaymentBehavior;
  churn_risk?: RiskLevel;
  scope_risk?: RiskLevel;
  billing_config: BillingConfig;
  notes?: string;
}

export interface ClientWithEventsResponse {
  client: Client;
  generated_events: CashEvent[];
}

// Expense Bucket Types
export interface ExpenseBucket {
  id: string;
  user_id: string;
  name: string;
  category: ExpenseCategory;
  bucket_type: BucketType;
  monthly_amount: string;
  currency: Currency;
  priority: Priority;
  is_stable: boolean;
  due_day: number;
  frequency: Frequency;
  employee_count: number | null;
  notes: string | null;
  // Sync fields
  source: SyncSource;
  xero_contact_id: string | null;
  xero_repeating_bill_id: string | null;
  quickbooks_vendor_id: string | null;
  sync_status: SyncStatus | null;
  last_synced_at: string | null;
  sync_error: string | null;
  locked_fields: string[];
  created_at: string;
  updated_at: string | null;
}

export interface ExpenseBucketCreate {
  user_id: string;
  name: string;
  category: ExpenseCategory;
  bucket_type: BucketType;
  monthly_amount: string;
  currency: Currency;
  priority: Priority;
  is_stable?: boolean;
  due_day?: number;
  frequency?: Frequency;
  employee_count?: number;
  notes?: string;
}

export interface ExpenseBucketWithEventsResponse {
  bucket: ExpenseBucket;
  generated_events: CashEvent[];
}

// Cash Event Types
export interface CashEvent {
  id: string;
  user_id: string;
  date: string;
  week_number: number;
  amount: string;
  direction: Direction;
  event_type: string;
  category: string;
  client_id: string | null;
  bucket_id: string | null;
  confidence: Confidence;
  confidence_reason: string | null;
  is_recurring: boolean;
  recurrence_pattern: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

// Forecast Types
export type ConfidenceLevel = 'high' | 'medium' | 'low';

export interface ForecastEventSummary {
  id: string;
  date: string;
  amount: string;
  direction: Direction;
  event_type: string;
  category: string | null;
  confidence: ConfidenceLevel;
  confidence_reason?: string;
  source_name?: string;
  source_type?: string;
}

export interface ConfidenceBreakdown {
  high: string;
  medium: string;
  low: string;
}

export interface WeekConfidenceBreakdown {
  cash_in: ConfidenceBreakdown;
  cash_out: ConfidenceBreakdown;
}

export interface ForecastWeek {
  week_number: number;
  week_start: string;
  week_end: string;
  starting_balance: string;
  cash_in: string;
  cash_out: string;
  net_change: string;
  ending_balance: string;
  events: ForecastEventSummary[];
  confidence_breakdown?: WeekConfidenceBreakdown;
}

export interface ForecastSummary {
  lowest_cash_week: number;
  lowest_cash_amount: string;
  total_cash_in: string;
  total_cash_out: string;
  runway_weeks: number;
}

export interface ConfidenceCountBreakdown {
  high_confidence_count: number;
  medium_confidence_count: number;
  low_confidence_count: number;
  high_confidence_amount: string;
  medium_confidence_amount: string;
  low_confidence_amount: string;
}

export interface ForecastConfidence {
  overall_score: string;
  overall_level: ConfidenceLevel;
  overall_percentage: number;
  breakdown: ConfidenceCountBreakdown;
  improvement_suggestions: string[];
}

export interface ForecastResponse {
  starting_cash: string;
  forecast_start_date: string;
  weeks: ForecastWeek[];
  summary: ForecastSummary;
  confidence?: ForecastConfidence;
}

// Scenario Types
export type ScenarioType =
  | 'client_loss'
  | 'client_gain'
  | 'client_change'
  | 'hiring'
  | 'firing'
  | 'contractor_gain'
  | 'contractor_loss'
  | 'increased_expense'
  | 'decreased_expense'
  | 'payment_delay_in'
  | 'payment_delay_out';

export type ScenarioStatus = 'draft' | 'active' | 'saved' | 'discarded' | 'confirmed';
export type EntryPath = 'user_defined' | 'tamio_suggested';

export interface Scenario {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  scenario_type: ScenarioType;
  entry_path: EntryPath;
  suggested_reason: string | null;
  scope_config: Record<string, unknown>;
  parameters: Record<string, unknown>;
  status: ScenarioStatus;
  parent_scenario_id: string | null;
  layer_order: number;
  created_at: string;
  updated_at: string | null;
}

export interface ScenarioCreate {
  user_id: string;
  name: string;
  description?: string;
  scenario_type: ScenarioType;
  entry_path: EntryPath;
  suggested_reason?: string;
  scope_config: Record<string, unknown>;
  parameters: Record<string, unknown>;
  parent_scenario_id?: string;
  layer_order?: number;
}

export interface ScenarioComparisonResponse {
  base_forecast: ForecastResponse;
  scenario_forecast: ForecastResponse;
  deltas: Record<string, unknown>;
  rule_evaluations: RuleEvaluation[];
  decision_signals: Record<string, unknown>;
  suggested_scenarios: ScenarioSuggestion[];
}

export interface RuleEvaluation {
  rule_id: string;
  rule_name: string;
  passed: boolean;
  breach_week: number | null;
  details: string;
}

export interface ScenarioSuggestion {
  scenario_type: ScenarioType;
  name: string;
  description: string;
  prefill_params: Record<string, unknown>;
  priority: 'high' | 'medium' | 'low';
}

// Financial Rules
export interface FinancialRule {
  id: string;
  user_id: string;
  rule_type: string;
  name: string;
  description: string | null;
  threshold_config: Record<string, unknown>;
  is_active: boolean;
  evaluation_scope: string;
  created_at: string;
  updated_at: string | null;
}

// TAMI Chat Types
export type ChatMode =
  | 'explain_forecast'
  | 'suggest_scenarios'
  | 'build_scenario'
  | 'goal_planning'
  | 'clarify';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface SuggestedAction {
  label: string;
  action: 'call_tool' | 'none';
  tool_name: string | null;
  tool_args: Record<string, unknown> | null;
}

export interface UIHints {
  show_scenario_banner: boolean;
  suggested_actions: SuggestedAction[];
}

export interface ChatResponseContent {
  message_markdown: string;
  mode: ChatMode;
  ui_hints: UIHints;
}

export interface ChatResponse {
  response: ChatResponseContent;
  context_summary: Record<string, unknown>;
  tool_calls_made: string[];
}

export interface ChatRequest {
  user_id: string;
  message: string;
  conversation_history: ChatMessage[];
  active_scenario_id: string | null;
}

// Xero Integration Types
export interface XeroConnectionStatus {
  is_connected: boolean;
  tenant_name: string | null;
  tenant_id: string | null;
  last_sync_at: string | null;
  token_expires_at: string | null;
  sync_error: string | null;
}

export interface XeroAuthUrl {
  auth_url: string;
  state: string;
}

export interface XeroSyncResult {
  success: boolean;
  sync_type: string;
  records_fetched: number;
  records_created: number;
  records_updated: number;
  records_skipped: number;
  started_at: string;
  completed_at: string;
}

// Onboarding Types
export interface OnboardingRequest {
  user: {
    email: string;
    base_currency: Currency;
  };
  cash_position: CashAccountInput[];
  clients: Omit<ClientCreate, 'user_id'>[];
  expenses: Omit<ExpenseBucketCreate, 'user_id'>[];
}

export interface OnboardingResponse {
  user_id: string;
  accounts_created: number;
  clients_created: number;
  expenses_created: number;
  events_generated: number;
}

// Obligation Types (3-Layer System)
export type ObligationType =
  | 'vendor_bill'
  | 'subscription'
  | 'payroll'
  | 'contractor'
  | 'loan_payment'
  | 'tax_obligation'
  | 'lease'
  | 'other';

export type AmountType = 'fixed' | 'variable' | 'milestone';
export type AmountSource = 'manual_entry' | 'xero_sync' | 'repeating_invoice' | 'contract_upload';
export type ScheduleStatus = 'scheduled' | 'due' | 'paid' | 'overdue' | 'cancelled';
export type PaymentStatus = 'pending' | 'completed' | 'failed' | 'reversed';
export type PaymentSource = 'manual_entry' | 'xero_sync' | 'bank_feed' | 'csv_import';

export interface ObligationAgreement {
  id: string;
  user_id: string;
  obligation_type: ObligationType;
  amount_type: AmountType;
  amount_source: AmountSource;
  base_amount: string;
  variability_rule: string | null;
  currency: Currency;
  frequency: Frequency;
  start_date: string;
  end_date: string | null;
  category: ExpenseCategory;
  account_id: string | null;
  confidence: Confidence;
  vendor_name: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface ObligationSchedule {
  id: string;
  obligation_id: string;
  due_date: string;
  period_start: string | null;
  period_end: string | null;
  estimated_amount: string;
  estimate_source: string;
  confidence: Confidence;
  status: ScheduleStatus;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface PaymentEvent {
  id: string;
  user_id: string;
  obligation_id: string | null;
  schedule_id: string | null;
  amount: string;
  currency: Currency;
  payment_date: string;
  account_id: string | null;
  status: PaymentStatus;
  source: PaymentSource;
  is_reconciled: boolean;
  reconciled_at: string | null;
  vendor_name: string | null;
  payment_method: string | null;
  reference: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

// API Error
export interface ApiError {
  detail: string;
  status?: number;
}

// =============================================================================
// Insights Types
// =============================================================================

// Income Behaviour
export interface ClientPaymentBehaviour {
  client_id: string;
  client_name: string;
  payment_behavior: PaymentBehavior;
  monthly_amount: string;
  percentage_of_revenue: string;
  risk_level: RiskLevel;
}

export interface RevenueConcentration {
  client_id: string;
  client_name: string;
  monthly_amount: string;
  percentage: string;
  is_high_concentration: boolean;
}

export interface IncomeBehaviourInsights {
  total_monthly_revenue: string;
  clients_with_delayed_payments: number;
  clients_with_high_concentration: number;
  revenue_at_risk_percentage: string;
  payment_behaviour: ClientPaymentBehaviour[];
  revenue_concentration: RevenueConcentration[];
  recommendations: string[];
}

// Expense Behaviour
export interface ExpenseCategoryTrend {
  category: string;
  current_monthly: string;
  previous_monthly: string;
  change_percentage: string;
  trend: 'rising' | 'stable' | 'declining';
  is_over_budget: boolean;
  budget_variance: string;
}

export interface ExpenseBucketDetail {
  bucket_id: string;
  name: string;
  category: string;
  monthly_amount: string;
  bucket_type: BucketType;
  priority: string;
  is_stable: boolean;
}

export interface ExpenseBehaviourInsights {
  total_monthly_expenses: string;
  fixed_expenses: string;
  variable_expenses: string;
  categories_rising: number;
  categories_over_budget: number;
  category_trends: ExpenseCategoryTrend[];
  expense_details: ExpenseBucketDetail[];
  recommendations: string[];
}

// Cash Discipline
export interface UpcomingRiskWindow {
  week_number: number;
  week_start: string;
  projected_balance: string;
  target_buffer: string;
  shortfall: string;
  severity: 'warning' | 'critical';
  contributing_factors: string[];
}

export interface CashDisciplineInsights {
  current_buffer: string;
  target_buffer: string;
  buffer_months: number;
  buffer_health_score: number;
  buffer_status: 'healthy' | 'at_risk' | 'critical';
  days_below_target_last_90: number;
  buffer_trend: 'improving' | 'stable' | 'declining';
  upcoming_risks: UpcomingRiskWindow[];
  weeks_until_risk: number | null;
  recommendations: string[];
}

// Traffic Light Status (TAMI Knowledge Framework)
export interface TrafficLightCondition {
  condition: string;
  met: boolean;
  severity: 'green' | 'amber' | 'red';
}

export interface TrafficLightStatus {
  status: 'green' | 'amber' | 'red';
  label: string; // "Stable", "Watch Closely", "Action Required"
  meaning: string;
  conditions_met: TrafficLightCondition[];
  guidance: string[];
  tami_message: string;
  action_window: string | null;
  urgency: 'none' | 'low' | 'medium' | 'high';
}

// Summary
export interface InsightsSummary {
  traffic_light: TrafficLightStatus;
  income_health_score: number;
  expense_health_score: number;
  cash_discipline_score: number;
  overall_health_score: number;
  alerts: string[];
  top_recommendations: string[];
}

// Complete Response
export interface InsightsResponse {
  summary: InsightsSummary;
  income_behaviour: IncomeBehaviourInsights;
  expense_behaviour: ExpenseBehaviourInsights;
  cash_discipline: CashDisciplineInsights;
}

// =============================================================================
// Behavior Insights Types (Phase 4)
// =============================================================================

export type TriggerSeverity = 'low' | 'medium' | 'high' | 'critical';
export type TriggerStatus = 'pending' | 'active' | 'dismissed' | 'deferred' | 'expired';
export type MetricTrend = 'improving' | 'stable' | 'worsening';

// Client Behavior
export interface ClientConcentration {
  client_id: string;
  client_name: string;
  cash_weighted_share: number;
  is_high_concentration: boolean;
}

export interface ClientPaymentReliability {
  client_id: string;
  client_name: string;
  score: number;
  mean: number;
  variance: number;
  trend: MetricTrend;
  trend_velocity: number;
  days_late_avg: number;
}

export interface RevenueAtRisk {
  total_30_day: string;
  total_60_day: string;
  by_client: Array<{
    client_id: string;
    client_name: string;
    amount_at_risk: string;
    probability: number;
    reason: string;
  }>;
}

export interface ClientBehaviorInsights {
  concentration: {
    top_client_share: number;
    top_3_share: number;
    hhi_score: number;
    clients: ClientConcentration[];
  };
  payment_reliability: ClientPaymentReliability[];
  revenue_at_risk: RevenueAtRisk;
}

// Expense Behavior
export interface CategoryVolatility {
  category: string;
  mean: number;
  variance: number;
  std_dev: number;
  trend: MetricTrend;
  drift_pct: number;
}

export interface ExpenseBehaviorInsights {
  volatility: CategoryVolatility[];
  discretionary_ratio: {
    discretionary_pct: number;
    essential_pct: number;
    trend: MetricTrend;
  };
  upcoming_commitments: Array<{
    id: string;
    name: string;
    amount: string;
    due_date: string;
    category: string;
  }>;
}

// Cash Discipline
export interface BufferIntegrity {
  current_buffer: string;
  target_buffer: string;
  buffer_ratio: number;
  days_below_threshold: number;
  trend: MetricTrend;
}

export interface CashDisciplineBehaviorInsights {
  buffer_integrity: BufferIntegrity;
  burn_momentum: {
    current_rate: number;
    weekly_change: number;
    trend: MetricTrend;
  };
  decision_rate: {
    reactive_count: number;
    deliberate_count: number;
    reactive_ratio: number;
    trend: MetricTrend;
  };
}

// Triggered Scenario
export interface TriggeredScenario {
  id: string;
  trigger_name: string;
  trigger_description: string;
  scenario_name: string;
  scenario_description: string;
  scenario_type: ScenarioType;
  scenario_parameters: Record<string, unknown>;
  severity: TriggerSeverity;
  estimated_impact: {
    cash_impact: number;
    weeks_affected: number;
    buffer_impact_pct: number;
    description: string;
  } | null;
  recommended_actions: string[];
  status: TriggerStatus;
  triggered_at: string;
  expires_at: string | null;
}

// Behavior Metrics
export interface BehaviorMetric {
  id: string;
  user_id: string;
  metric_type: string;
  entity_type: string | null;
  entity_id: string | null;
  current_value: number;
  previous_value: number | null;
  mean: number | null;
  variance: number | null;
  std_dev: number | null;
  trend: MetricTrend;
  trend_velocity: number | null;
  trend_confidence: number | null;
  threshold_warning: number | null;
  threshold_critical: number | null;
  is_higher_better: boolean;
  is_breached: boolean;
  is_warning: boolean;
  data_confidence: number;
  context_data: Record<string, unknown>;
  computed_at: string;
}

// Complete Behavior Response
export interface BehaviorInsightsResponse {
  health_score: number;
  health_label: 'Healthy' | 'At Risk' | 'Critical';
  client_behavior: ClientBehaviorInsights;
  expense_behavior: ExpenseBehaviorInsights;
  cash_discipline: CashDisciplineBehaviorInsights;
  triggered_scenarios: TriggeredScenario[];
  pending_scenarios_count: number;
}

// Trigger Action
export interface TriggeredScenarioAction {
  action: 'run_scenario' | 'dismiss' | 'defer';
  notes?: string;
}
