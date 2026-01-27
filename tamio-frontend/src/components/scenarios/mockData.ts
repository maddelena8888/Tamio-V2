// Mock data for Scenario Builder - Phase 1
// This will be replaced with API calls in Phase 2

export type ScenarioType =
  | 'payment_delay_in'
  | 'payment_delay_out'
  | 'client_loss'
  | 'client_gain'
  | 'hiring'
  | 'firing'
  | 'contractor_gain'
  | 'contractor_loss'
  | 'increased_expense'
  | 'decreased_expense';

export type BuilderMode = 'suggested' | 'manual';

export interface VariableOption {
  value: string;
  label: string;
}

export interface ScenarioVariable {
  key: string;
  options: VariableOption[];
  defaultValue: string;
  type?: 'select' | 'date';
}

export interface MockSuggestedScenario {
  id: string;
  template: string;
  variables: ScenarioVariable[];
  scenarioType: ScenarioType;
  reason?: string;
}

export const MOCK_SUGGESTED_SCENARIOS: MockSuggestedScenario[] = [
  {
    id: '1',
    template: 'What if {client} pays {days} late?',
    variables: [
      {
        key: 'client',
        options: [
          { value: 'retailco-rebrand', label: 'RetailCo Rebrand' },
          { value: 'techcorp', label: 'TechCorp' },
          { value: 'healthtech', label: 'HealthTech Campaign' },
        ],
        defaultValue: 'retailco-rebrand',
      },
      {
        key: 'days',
        options: [
          { value: '14', label: '14 days' },
          { value: '30', label: '30 days' },
          { value: '60', label: '60 days' },
          { value: '90', label: '90 days' },
        ],
        defaultValue: '30',
      },
    ],
    scenarioType: 'payment_delay_in',
    reason: 'Based on alert: RetailCo payment 14 days overdue',
  },
  {
    id: '2',
    template: 'Can we afford to hire a {role} starting on {date} with a salary of {salary}?',
    variables: [
      {
        key: 'role',
        options: [
          { value: 'product-designer', label: 'Product Designer' },
          { value: 'senior-developer', label: 'Senior Developer' },
          { value: 'sales-rep', label: 'Sales Rep' },
        ],
        defaultValue: 'product-designer',
      },
      {
        key: 'date',
        options: [
          { value: '2026-03-01', label: 'March 1st' },
          { value: '2026-04-01', label: 'April 1st' },
          { value: '2026-05-01', label: 'May 1st' },
        ],
        defaultValue: '2026-03-01',
        type: 'date',
      },
      {
        key: 'salary',
        options: [
          { value: '60000', label: '$60,000/yr' },
          { value: '85000', label: '$85,000/yr' },
          { value: '100000', label: '$100,000/yr' },
          { value: '120000', label: '$120,000/yr' },
        ],
        defaultValue: '85000',
      },
    ],
    scenarioType: 'hiring',
    reason: 'Based on hiring scenarios in your ledger projections',
  },
  {
    id: '3',
    template: 'What if {expense} increases {percentage}?',
    variables: [
      {
        key: 'expense',
        options: [
          { value: 'aws', label: 'AWS Infrastructure' },
          { value: 'marketing', label: 'Marketing spend' },
          { value: 'software', label: 'Software subscriptions' },
        ],
        defaultValue: 'aws',
      },
      {
        key: 'percentage',
        options: [
          { value: '15', label: '15%' },
          { value: '25', label: '25%' },
          { value: '50', label: '50%' },
        ],
        defaultValue: '25',
      },
    ],
    scenarioType: 'increased_expense',
    reason: 'Based on high infrastructure costs in recent weeks',
  },
  {
    id: '4',
    template: 'What if we lose {client} as a client?',
    variables: [
      {
        key: 'client',
        options: [
          { value: 'techcorp', label: 'TechCorp' },
          { value: 'retailco', label: 'RetailCo' },
          { value: 'healthtech', label: 'HealthTech Campaign' },
        ],
        defaultValue: 'techcorp',
      },
    ],
    scenarioType: 'client_loss',
    reason: 'Based on client concentration risk analysis',
  },
  {
    id: '5',
    template: 'What if we delay payment to {vendor} by {days}?',
    variables: [
      {
        key: 'vendor',
        options: [
          { value: 'aws', label: 'AWS' },
          { value: 'figma', label: 'Figma' },
          { value: 'office', label: 'Office lease' },
        ],
        defaultValue: 'aws',
      },
      {
        key: 'days',
        options: [
          { value: '15', label: '15 days' },
          { value: '30', label: '30 days' },
          { value: '45', label: '45 days' },
        ],
        defaultValue: '30',
      },
    ],
    scenarioType: 'payment_delay_out',
    reason: 'Outbound payment timing optimization',
  },
];

export const SCENARIO_TYPE_OPTIONS: { value: ScenarioType; label: string }[] = [
  { value: 'payment_delay_in', label: 'Payment Delay (Incoming)' },
  { value: 'payment_delay_out', label: 'Payment Delay (Outgoing)' },
  { value: 'client_loss', label: 'Client Loss' },
  { value: 'client_gain', label: 'Client Gain' },
  { value: 'hiring', label: 'New Hire' },
  { value: 'firing', label: 'Layoff / Termination' },
  { value: 'contractor_gain', label: 'Add Contractor' },
  { value: 'contractor_loss', label: 'Remove Contractor' },
  { value: 'increased_expense', label: 'Expense Increase' },
  { value: 'decreased_expense', label: 'Expense Decrease' },
];

// ============================================================================
// SCENARIO PARAMETER TYPES
// ============================================================================

export interface PaymentDelayParams {
  delayWeeks: number; // 1-52
  partialPaymentPct?: number; // 0-100, optional
  clientOrVendor: string; // ID of the client/vendor
}

export interface ClientLossParams {
  clientId: string;
  effectiveDate: string;
  impactRetainers: boolean;
  impactMilestones: boolean;
  reduceVariableCosts?: number; // percentage reduction, optional
}

export interface ClientGainParams {
  clientName: string;
  startDate: string;
  agreementType: 'retainer' | 'project' | 'usage' | 'mixed';
  monthlyAmount: number;
  billingFrequency: 'monthly' | 'quarterly' | 'annual';
  addVariableCosts?: number; // optional additional costs
}

export interface HiringParams {
  roleTitle: string;
  startDate: string;
  monthlyCost: number;
  payFrequency: 'monthly' | 'bi-weekly' | 'weekly';
  onboardingCosts?: number; // optional
}

export interface FiringParams {
  employeeId?: string; // optional, for tracking specific employee
  endDate: string;
  monthlyCost: number;
  severanceAmount?: number; // optional
}

export interface ContractorParams {
  contractorName?: string; // optional
  date: string; // start date for gain, end date for loss
  monthlyEstimate: number;
  isRecurring: boolean;
}

export interface ExpenseParams {
  expenseName: string;
  amount: number;
  effectiveDate: string;
  isRecurring: boolean;
  frequency?: 'monthly' | 'quarterly' | 'annual'; // optional, only if recurring
}

export type ScenarioParams =
  | { type: 'payment_delay_in' | 'payment_delay_out'; params: PaymentDelayParams }
  | { type: 'client_loss'; params: ClientLossParams }
  | { type: 'client_gain'; params: ClientGainParams }
  | { type: 'hiring'; params: HiringParams }
  | { type: 'firing'; params: FiringParams }
  | { type: 'contractor_gain' | 'contractor_loss'; params: ContractorParams }
  | { type: 'increased_expense' | 'decreased_expense'; params: ExpenseParams };

// Mock client/vendor data for selectors
export const MOCK_CLIENTS = [
  { id: 'techcorp', name: 'TechCorp' },
  { id: 'retailco', name: 'RetailCo' },
  { id: 'healthtech', name: 'HealthTech Campaign' },
  { id: 'finserv', name: 'FinServ Solutions' },
];

export const MOCK_VENDORS = [
  { id: 'aws', name: 'AWS' },
  { id: 'figma', name: 'Figma' },
  { id: 'slack', name: 'Slack' },
  { id: 'office-lease', name: 'Office Lease' },
];

export const MOCK_EMPLOYEES = [
  { id: 'emp-001', name: 'John Smith - Senior Developer' },
  { id: 'emp-002', name: 'Jane Doe - Product Designer' },
  { id: 'emp-003', name: 'Mike Johnson - Sales Rep' },
];
