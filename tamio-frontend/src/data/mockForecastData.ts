// Mock data for Forecast Canvas page
// Extracted from tamio-v3-figma-model.html mockup

export type ConfidenceLevel = 'confirmed' | 'probable' | 'speculative';
export type ObligationStatus = 'on-track' | 'behind' | 'warning';
export type AlertTier = 'act-now' | 'monitor';
export type RuleStatus = 'passing' | 'at-risk';

export interface MetricData {
  value: number;
  confidence: ConfidenceLevel;
  source?: string;
  updatedAgo?: string;
  unit?: string;
}

export interface ObligationItem {
  name: string;
  status: ObligationStatus;
}

export interface ForecastPoint {
  date: string;
  position: number;
  cashIn: number;
  cashOut: number;
  confidence: ConfidenceLevel;
  x: number; // percentage position on chart
  y: number; // percentage position on chart
}

export interface Scenario {
  id: string;
  name: string;
  impact: string;
  color: ConfidenceLevel;
  active: boolean;
}

export interface Alert {
  id: string;
  tier: AlertTier;
  type: 'overdue' | 'upcoming';
  title: string;
  subtitle: string;
  body: string;
  primaryAction?: string;
  secondaryAction?: string;
}

export interface ActivityItem {
  id: string;
  type: 'payment' | 'update' | 'rule';
  text: string;
  highlight?: string;
  time: string;
}

export interface Rule {
  id: string;
  name: string;
  current: string;
  threshold: string;
  status: RuleStatus;
}

export interface Comment {
  id: string;
  author: string;
  avatar: string;
  avatarColor: string;
  time: string;
  body: string;
  x: number;
  y: number;
}

export interface DailySummaryItem {
  type: 'positive' | 'negative' | 'neutral';
  text: string;
  value: string;
}

// Mock Metrics
export const mockMetrics = {
  cashNow: {
    value: 247000,
    confidence: 'confirmed' as ConfidenceLevel,
    source: 'Starling',
    updatedAgo: '2 min',
  },
  obligations: {
    value: 41200,
    confidence: 'probable' as ConfidenceLevel,
    items: [
      { name: 'VAT', status: 'on-track' as ObligationStatus },
      { name: 'Corp Tax', status: 'behind' as ObligationStatus },
      { name: 'Payroll', status: 'on-track' as ObligationStatus },
    ],
  },
  availableCash: {
    value: 205800,
    confidence: 'confirmed' as ConfidenceLevel,
  },
  runway: {
    value: 13,
    unit: 'weeks',
    confidence: 'probable' as ConfidenceLevel,
  },
};

// Mock Forecast Data Points
export const mockForecastData: ForecastPoint[] = [
  { date: 'Today', position: 247000, cashIn: 15400, cashOut: 8200, confidence: 'confirmed', x: 0, y: 42 },
  { date: 'Feb 10', position: 258400, cashIn: 24000, cashOut: 12600, confidence: 'confirmed', x: 12.5, y: 39 },
  { date: 'Feb 17', position: 262800, cashIn: 18200, cashOut: 13800, confidence: 'confirmed', x: 25, y: 38 },
  { date: 'Feb 24', position: 275000, cashIn: 32000, cashOut: 19800, confidence: 'probable', x: 37.5, y: 35 },
  { date: 'Mar 3', position: 247200, cashIn: 8500, cashOut: 36300, confidence: 'probable', x: 50, y: 42 },
  { date: 'Mar 10', position: 218400, cashIn: 5200, cashOut: 34000, confidence: 'speculative', x: 62.5, y: 48 },
  { date: 'Mar 17', position: 185600, cashIn: 12000, cashOut: 44800, confidence: 'speculative', x: 75, y: 52 },
  { date: 'Mar 24', position: 198200, cashIn: 28600, cashOut: 16000, confidence: 'speculative', x: 87.5, y: 50 },
];

// Mock Scenarios
export const mockScenarios: Scenario[] = [
  { id: '1', name: '+ Hire (Mar)', impact: '-4w', color: 'probable', active: false },
  { id: '2', name: 'Acme pays late', impact: '-2w', color: 'speculative', active: false },
  { id: '3', name: 'TechCorp closes', impact: '+3w', color: 'confirmed', active: false },
];

// Mock Alerts
export const mockAlerts: Alert[] = [
  {
    id: '1',
    tier: 'act-now',
    type: 'overdue',
    title: 'Acme Corp overdue',
    subtitle: 'Invoice #1247 • £15,400',
    body: '12 days overdue. Based on their history, 78% chance they pay this week.',
    primaryAction: 'Send Reminder',
    secondaryAction: 'Dismiss',
  },
  {
    id: '2',
    tier: 'monitor',
    type: 'upcoming',
    title: 'VAT payment due',
    subtitle: 'In 8 days • £18,200',
    body: 'Funds have been set aside in your forecast. Currently 65% reserved.',
    secondaryAction: 'View Details',
  },
];

// Mock Activity
export const mockActivity: ActivityItem[] = [
  {
    id: '1',
    type: 'payment',
    text: 'received from TechFlow Ltd',
    highlight: '£15,400',
    time: '3 hours ago',
  },
  {
    id: '2',
    type: 'update',
    text: 'Forecast recalculated. Runway now',
    highlight: '13 weeks',
    time: '3 hours ago',
  },
  {
    id: '3',
    type: 'rule',
    text: 'Daily rule check passed. All thresholds healthy.',
    time: '6 hours ago',
  },
];

// Mock Rules
export const mockRules: Rule[] = [
  {
    id: '1',
    name: 'Minimum Cash Buffer',
    current: '£205,800',
    threshold: '£50,000',
    status: 'passing',
  },
  {
    id: '2',
    name: 'Minimum Runway',
    current: '13 weeks',
    threshold: '8 weeks',
    status: 'passing',
  },
  {
    id: '3',
    name: 'Receivables Age',
    current: '47 days avg',
    threshold: '45 days',
    status: 'at-risk',
  },
];

// Mock Comments
export const mockComments: Comment[] = [
  {
    id: '1',
    author: 'Sarah Chen',
    avatar: 'S',
    avatarColor: '#6366f1',
    time: '15 min ago',
    body: 'Acme payment might slip 2 weeks. Should we adjust?',
    x: 43,
    y: 28,
  },
  {
    id: '2',
    author: 'TAMI',
    avatar: '✦',
    avatarColor: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
    time: '2 hours ago',
    body: "This assumes TechCorp closes. Without it, runway = 9 wks.",
    x: 72,
    y: 45,
  },
];

// Mock Daily Summary
export const mockDailySummary: DailySummaryItem[] = [
  { type: 'positive', text: 'Payment received', value: '+£15,400' },
  { type: 'negative', text: 'Invoice overdue', value: '1' },
  { type: 'neutral', text: 'Runway change', value: '+1 week' },
];

// Collaborators
export const mockCollaborators = [
  { id: '1', name: 'You', initials: 'M', color: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', online: true },
  { id: '2', name: 'Sarah', initials: 'S', color: '#6366f1', online: true },
  { id: '3', name: 'James', initials: 'J', color: '#ec4899', online: false },
];

// Confidence bands data for weekly ranges
export const mockConfidenceBands = [
  { week: 1, top: 38, height: 15 },
  { week: 2, top: 35, height: 18 },
  { week: 3, top: 32, height: 20 },
  { week: 4, top: 30, height: 22 },
  { week: 5, top: 32, height: 25 },
  { week: 6, top: 35, height: 28 },
  { week: 7, top: 40, height: 30 },
  { week: 8, top: 42, height: 32 },
  { week: 9, top: 40, height: 35 },
];

// X-axis labels
export const mockXAxisLabels = ['Today', 'Feb 10', 'Feb 17', 'Feb 24', 'Mar 3', 'Mar 10', 'Mar 17', 'Mar 24', 'Mar 31'];

// Y-axis labels
export const mockYAxisLabels = ['£400k', '£300k', '£200k', '£100k', '£0'];

// Rule threshold position (as percentage from top)
export const ruleThresholdPosition = 78; // 78% from top = £50k minimum buffer

// Helper function to format currency
export const formatCurrency = (value: number): string => {
  if (value >= 1000000) {
    return `£${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `£${(value / 1000).toFixed(0)}k`;
  }
  return `£${value.toLocaleString()}`;
};

// Helper function to format full currency
export const formatFullCurrency = (value: number): string => {
  return `£${value.toLocaleString()}`;
};

// Helper function to get confidence color
export const getConfidenceColor = (confidence: ConfidenceLevel): string => {
  switch (confidence) {
    case 'confirmed':
      return 'var(--canvas-confirmed)';
    case 'probable':
      return 'var(--canvas-probable)';
    case 'speculative':
      return 'var(--canvas-speculative)';
    default:
      return 'var(--canvas-text-muted)';
  }
};

// Helper function to get status color
export const getStatusColor = (status: ObligationStatus | RuleStatus): string => {
  switch (status) {
    case 'on-track':
    case 'passing':
      return 'var(--canvas-confirmed)';
    case 'behind':
    case 'at-risk':
      return 'var(--canvas-speculative)';
    case 'warning':
      return 'var(--canvas-probable)';
    default:
      return 'var(--canvas-text-muted)';
  }
};
