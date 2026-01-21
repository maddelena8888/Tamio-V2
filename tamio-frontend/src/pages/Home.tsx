/**
 * Home Page - Redesigned Layout
 *
 * Layout (top to bottom):
 * 1. Quick Metrics (3-column: Cash, Runway, Buffer)
 * 2. Two-column grid: Alerts & Actions | Prepared Actions
 * 3. Agent Activity (compact full-width)
 * 4. TAMI Chat (enlarged with suggested questions grid)
 *
 * Features:
 * - Clean card-based layout
 * - Left border severity indicators on alerts
 * - Suggested questions for TAMI interaction
 * - Contextual quick actions based on urgent problems
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { NeuroCard, NeuroCardContent } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  User,
  AlertTriangle,
  Check,
  BellOff,
  Bell,
  Loader2,
  Banknote,
  Timer,
  Shield,
  ArrowRight,
  TrendingDown,
  Expand,
} from 'lucide-react';
import { SeverityPill } from '@/components/ui/severity-pill';
import { StatusPill } from '@/components/ui/status-pill';
import { TamiExpandedModal } from '@/components/chat/TamiExpandedModal';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { sendChatMessageStreaming, formatConversationHistory } from '@/lib/api/tami';
import type { ChatMode, SuggestedAction } from '@/lib/api/types';
import ReactMarkdown from 'react-markdown';
import { StructuredResponse } from '@/components/chat/StructuredResponse';
import { getForecast } from '@/lib/api/forecast';
import { getCashPosition } from '@/lib/api/data';
import { getRules } from '@/lib/api/scenarios';
import {
  approveActionOption,
  dismissProblem,
  getActionQueueCounts,
  getAgentActivity,
  type Problem,
  type ActionQueueResponse,
  type AgentActivityStats,
} from '@/lib/api/actionMonitor';
import {
  getRisks,
  getControls,
  dismissRisk,
  approveControl,
  type Risk,
  type Control,
} from '@/lib/api/alertsActions';
import type { ForecastResponse, CashPositionResponse, FinancialRule } from '@/lib/api/types';

// ============================================================================
// Types
// ============================================================================

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  mode?: ChatMode;
  suggestedActions?: SuggestedAction[];
  showScenarioBanner?: boolean;
  isStreaming?: boolean;
  showInlineCards?: boolean;
}

type Severity = 'urgent' | 'high' | 'normal';

// Type for prepared actions displayed on homepage
interface PreparedActionSummary {
  id: string;
  title: string;
  description: string;
  impact: string;
  impactAmount?: number; // Raw numeric value for determining color (positive = green, negative = red)
  status: 'pending' | 'in_progress' | 'approved' | 'completed';
  whyItMatters?: string;
  tamioHandles?: string[];
  userHandles?: string[];
}

// ============================================================================
// Style Configurations
// ============================================================================

const severityConfig: Record<Severity, { label: string; bgClass: string; textClass: string; borderClass: string }> = {
  urgent: {
    label: 'Urgent',
    bgClass: 'bg-tomato/10',
    textClass: 'text-tomato',
    borderClass: 'border-tomato/30',
  },
  high: {
    label: 'High',
    bgClass: 'bg-yellow-500/10',
    textClass: 'text-yellow-700',
    borderClass: 'border-yellow-500/30',
  },
  normal: {
    label: 'Medium',
    bgClass: 'bg-lime/10',
    textClass: 'text-lime-700',
    borderClass: 'border-lime/30',
  },
};

// ============================================================================
// Mock Data
// ============================================================================

// Diverse Mock Problems showcasing platform capabilities:
// - Client payment tracking & collection
// - Vendor negotiations & payment optimization
// - Hiring/staffing financial impact
// - Proactive cash management
// - Scenario-based recommendations
const MOCK_PROBLEMS: Problem[] = [
  {
    id: 'problem-1',
    title: 'Payment 14 days overdue: RetailCo Rebrand',
    severity: 'urgent',
    detected_at: new Date().toISOString(),
    trigger: 'Invoice Scanner',
    context: [
      'RetailCo\'s Design milestone payment ($52,500) is 14 days overdue',
      '35% of buffer at risk ($53K shortfall impact)',
      'Client usually pays within 7 days - this is unusual behavior',
    ],
    actions: [
      {
        id: 'action-1a',
        title: 'Send gentle reminder',
        description: 'First follow-up email on outstanding payment',
        risk_level: 'low',
        is_recommended: true,
        reasoning: ['Maintains relationship', 'Client has good payment history', '85% success rate for gentle reminders'],
        cash_impact: 52500,
        impact_description: 'Recovers full outstanding amount',
        prepared_content: {
          email_subject: 'Quick follow-up: Invoice #1247',
          email_body: 'Hi Sarah, Hope all is well! I wanted to check in on invoice #1247 for the Design milestone...',
          recipient: 'sarah@retailco.com',
        },
        status: 'pending',
        success_probability: 0.85,
      },
      {
        id: 'action-1b',
        title: 'Resend invoice',
        description: 'In case original was missed or lost',
        risk_level: 'low',
        is_recommended: false,
        reasoning: ['Simple first step', 'Covers case where email was missed'],
        cash_impact: 52500,
        impact_description: 'Recovers full outstanding amount',
        prepared_content: { description: 'Resend invoice #1247 with payment details' },
        status: 'pending',
        success_probability: 0.6,
      },
    ],
  },
  {
    id: 'problem-2',
    title: 'New hire impact: Senior Developer start date Monday',
    severity: 'high',
    detected_at: new Date(Date.now() - 86400000).toISOString(),
    trigger: 'Forecast Engine',
    context: [
      'Alex Chen starts Monday - $12,500/month salary + benefits',
      'Increases monthly burn by 8.3% ($150K annually)',
      'Runway drops from 14 weeks to 11 weeks',
    ],
    actions: [
      {
        id: 'action-2a',
        title: 'Confirm onboarding budget',
        description: 'Review and approve equipment, software, and first month costs',
        risk_level: 'low',
        is_recommended: true,
        reasoning: ['Equipment budget $3,500 already allocated', 'No unexpected costs detected'],
        cash_impact: -16000,
        impact_description: 'First month total cost',
        prepared_content: {
          description: 'Onboarding checklist: MacBook Pro ($2,400), monitors ($600), software licenses ($500)',
        },
        status: 'pending',
        success_probability: 1.0,
      },
      {
        id: 'action-2b',
        title: 'Accelerate client invoicing',
        description: 'Send pending invoices early to offset new costs',
        risk_level: 'low',
        is_recommended: false,
        reasoning: ['$28K in invoices ready to send', 'Can improve cash timing'],
        cash_impact: 28000,
        impact_description: 'Accelerates cash inflow',
        prepared_content: { description: 'Batch invoice for TechCorp Q1 deliverables' },
        status: 'pending',
        success_probability: 0.95,
      },
    ],
  },
  {
    id: 'problem-3',
    title: 'Vendor rate increase: Figma renewal +40%',
    severity: 'high',
    detected_at: new Date(Date.now() - 43200000).toISOString(),
    trigger: 'Expense Monitor Agent',
    context: [
      'Figma annual renewal increased from $3,600 to $5,040 (+40%)',
      'Auto-renewal in 12 days if no action taken',
      'Team only using 60% of current seat allocation',
    ],
    actions: [
      {
        id: 'action-3a',
        title: 'Negotiate lower rate',
        description: 'Contact Figma to discuss enterprise pricing or seat reduction',
        risk_level: 'low',
        is_recommended: true,
        reasoning: ['40% of seats unused', 'Negotiation typically yields 15-25% savings', 'Competitor alternatives available'],
        cash_impact: -1260,
        impact_description: 'Est. annual savings with negotiation',
        prepared_content: {
          email_subject: 'Renewal Discussion - Account #F8892',
          email_body: 'Hi Figma Team, We\'re reviewing our renewal and noticed we\'re not fully utilizing our seat allocation...',
        },
        status: 'pending',
        success_probability: 0.7,
      },
      {
        id: 'action-3b',
        title: 'Right-size plan',
        description: 'Reduce to 8 seats from current 12',
        risk_level: 'medium',
        is_recommended: false,
        reasoning: ['Saves $1,680/year', 'Requires confirming with team leads'],
        cash_impact: -1680,
        impact_description: 'Annual savings from seat reduction',
        prepared_content: { description: 'Audit current Figma usage and identify inactive seats' },
        status: 'pending',
        success_probability: 0.9,
      },
    ],
  },
  {
    id: 'problem-4',
    title: 'Opportunity: Early payment discount from GlobalTech',
    severity: 'normal',
    detected_at: new Date(Date.now() - 172800000).toISOString(),
    trigger: 'Cash Optimizer',
    context: [
      'GlobalTech offering 2% discount for payment within 10 days',
      'Invoice: $45,000 - potential savings: $900',
      'Cash position supports early payment with buffer maintained',
    ],
    actions: [
      {
        id: 'action-4a',
        title: 'Take early payment discount',
        description: 'Pay $44,100 now instead of $45,000 in 30 days',
        risk_level: 'low',
        is_recommended: true,
        reasoning: ['2% discount = 24% annualized return', 'Buffer remains above minimum', 'Strong cash position'],
        cash_impact: 900,
        impact_description: 'Savings from early payment',
        prepared_content: { description: 'Process payment of $44,100 to GlobalTech by Friday' },
        status: 'pending',
        success_probability: 1.0,
      },
    ],
  },
  {
    id: 'problem-5',
    title: 'Client contract ending: HealthTech Phase 1',
    severity: 'normal',
    detected_at: new Date(Date.now() - 259200000).toISOString(),
    trigger: 'Revenue Monitor',
    context: [
      'HealthTech Phase 1 contract ($18K/month) ends in 6 weeks',
      'No Phase 2 contract signed yet',
      'Represents 12% of monthly revenue',
    ],
    actions: [
      {
        id: 'action-5a',
        title: 'Send Phase 2 proposal',
        description: 'Proactive outreach with scope and pricing for continued engagement',
        risk_level: 'low',
        is_recommended: true,
        reasoning: ['Strong relationship', 'Phase 1 delivered on time', 'Client mentioned expansion interest'],
        cash_impact: 54000,
        impact_description: '3-month Phase 2 contract value',
        prepared_content: {
          email_subject: 'Phase 2 Proposal - HealthTech Platform',
          email_body: 'Hi Jennifer, As we wrap up Phase 1, I wanted to share our proposal for the next phase...',
        },
        status: 'pending',
        success_probability: 0.75,
      },
      {
        id: 'action-5b',
        title: 'Run revenue impact scenario',
        description: 'Model cash flow if contract not renewed',
        risk_level: 'low',
        is_recommended: false,
        reasoning: ['Understand worst-case runway', 'Plan contingencies'],
        cash_impact: 0,
        impact_description: 'Planning scenario only',
        prepared_content: { description: 'Create scenario: HealthTech contract ends without renewal' },
        status: 'pending',
        success_probability: 1.0,
      },
    ],
  },
];

// ============================================================================
// Data Transformation Functions (Risk/Control -> Problem/PreparedAction)
// These transform the V4 alerts-actions API data to match the homepage display format
// ============================================================================

/**
 * Transform a Risk from the alerts-actions API to a Problem for homepage display
 */
function transformRiskToProblem(risk: Risk, linkedControls: Control[]): Problem {
  // Map severity
  const severity = risk.severity as Severity;

  // Build actions from linked controls
  const actions = linkedControls.map((control, index) => ({
    id: control.id,
    title: control.name,
    description: control.why_it_exists,
    risk_level: 'medium' as const,
    is_recommended: index === 0, // First control is recommended
    reasoning: control.tamio_handles,
    cash_impact: control.impact_amount,
    impact_description: control.impact_amount
      ? `${control.impact_amount >= 0 ? '+' : ''}$${Math.abs(control.impact_amount).toLocaleString()}`
      : null,
    prepared_content: control.draft_content,
    status: control.state === 'pending' ? 'pending' as const : 'approved' as const,
    success_probability: 0.8,
  }));

  return {
    id: risk.id,
    title: risk.title,
    severity,
    detected_at: risk.detected_at,
    trigger: `${risk.detection_type} Detection`,
    context: risk.context_bullets.length > 0 ? risk.context_bullets : [risk.primary_driver],
    actions,
  };
}

/**
 * Transform a Control from the alerts-actions API to a PreparedActionSummary for homepage display
 */
function transformControlToPreparedAction(control: Control): PreparedActionSummary {
  // Map control state to status
  const statusMap: Record<string, 'pending' | 'in_progress' | 'approved' | 'completed'> = {
    pending: 'pending',
    active: 'in_progress',
    completed: 'completed',
    needs_review: 'pending',
  };

  return {
    id: control.id,
    title: control.name,
    description: control.why_it_exists,
    impact: control.impact_amount
      ? `${control.impact_amount >= 0 ? '+' : ''}$${Math.abs(control.impact_amount / 1000).toFixed(0)}K`
      : '',
    impactAmount: control.impact_amount ?? undefined,
    status: statusMap[control.state] || 'pending',
    whyItMatters: control.why_it_exists,
    tamioHandles: control.tamio_handles,
    userHandles: control.user_handles,
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

const formatAmount = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '$0';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.abs(value));
};

const formatCompactAmount = (value: number): string => {
  if (Math.abs(value) >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1000) {
    return `$${(value / 1000).toFixed(0)}K`;
  }
  return `$${value.toFixed(0)}`;
};

// OBLIGATION-FOCUSED: Generate contextual questions about obligations, not clients
const generateContextualQuestion = (problem: Problem): string => {
  const title = problem.title.toLowerCase();

  // Payroll obligations
  if (title.includes('payroll')) {
    if (title.includes('underfunded')) {
      return 'Am I covered for Friday payroll?';
    }
    return 'Can we safely cover payroll this week?';
  }

  // Tax/VAT obligations
  if (title.includes('vat') || title.includes('tax')) {
    if (title.includes('at risk')) {
      return 'Will we have enough for the tax payment?';
    }
    return 'Are our tax obligations covered?';
  }

  // Rent/fixed costs
  if (title.includes('rent') || title.includes('office')) {
    return 'Is rent covered this month?';
  }

  // Buffer/cash concerns
  if (title.includes('buffer')) {
    return 'What\'s the status of our cash buffer?';
  }

  // AWS/vendor payments
  if (title.includes('aws') || title.includes('payment approaching')) {
    return 'What payments are coming up?';
  }

  // Generic obligation-focused question
  if (title.includes('underfunded') || title.includes('at risk')) {
    return 'What obligations need attention?';
  }

  return `Tell me about: ${problem.title}`;
};

// ============================================================================
// Inline KPI Cards Component (for chat responses)
// ============================================================================

interface InlineKPICardsProps {
  availableCash: number;
  runwayWeeks: number;
  bufferStatus: 'Safe' | 'At Risk' | 'Urgent';
}

function InlineKPICards({ availableCash, runwayWeeks, bufferStatus }: InlineKPICardsProps) {
  const bufferColors = {
    Safe: { bg: 'bg-lime/10', text: 'text-lime-700', dot: 'bg-lime-500' },
    'At Risk': { bg: 'bg-yellow-500/10', text: 'text-yellow-700', dot: 'bg-yellow-500' },
    Urgent: { bg: 'bg-tomato/10', text: 'text-tomato', dot: 'bg-tomato' },
  };
  const { bg, text, dot } = bufferColors[bufferStatus];

  return (
    <div className="grid grid-cols-3 gap-2 my-3">
      <div className="p-3 rounded-lg bg-blue-50/80 border border-blue-100">
        <div className="flex items-center gap-1.5 mb-1">
          <Banknote className="w-3.5 h-3.5 text-blue-600" />
          <span className="text-[10px] uppercase tracking-wide text-blue-600 font-medium">Cash</span>
        </div>
        <div className="text-lg font-bold text-blue-900">{formatCompactAmount(availableCash)}</div>
      </div>
      <div className="p-3 rounded-lg bg-purple-50/80 border border-purple-100">
        <div className="flex items-center gap-1.5 mb-1">
          <Timer className="w-3.5 h-3.5 text-purple-600" />
          <span className="text-[10px] uppercase tracking-wide text-purple-600 font-medium">Runway</span>
        </div>
        <div className="text-lg font-bold text-purple-900">{runwayWeeks > 52 ? '52+' : runwayWeeks} wks</div>
      </div>
      <div className={cn('p-3 rounded-lg border', bg, 'border-opacity-50')}>
        <div className="flex items-center gap-1.5 mb-1">
          <Shield className="w-3.5 h-3.5" />
          <span className="text-[10px] uppercase tracking-wide font-medium">Buffer</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={cn('w-2 h-2 rounded-full', dot)} />
          <span className={cn('text-lg font-bold', text)}>{bufferStatus}</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// TAMI Chat Components
// ============================================================================

const TypingIndicator = () => (
  <div className="flex items-center gap-1.5 py-1">
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce [animation-delay:-0.3s]" />
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce [animation-delay:-0.15s]" />
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce" />
  </div>
);

// ============================================================================
// Problem Detail Modal
// ============================================================================

interface ProblemDetailModalProps {
  problem: Problem | null;
  onClose: () => void;
  onApprove: (actionId: string) => void;
  onDismiss: () => void;
  onSnooze: (days: number) => void;
  loadingActionId?: string | null;
}

function ProblemDetailModal({ problem, onClose, onApprove, onDismiss, onSnooze, loadingActionId }: ProblemDetailModalProps) {
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [snoozeOpen, setSnoozeOpen] = useState(false);

  if (!problem) return null;

  const severity = (problem.severity as Severity) || 'normal';
  const config = severityConfig[severity];
  const cashAtRisk = problem.actions?.[0]?.cash_impact || 0;
  const recommendedAction = problem.actions?.find(a => a.is_recommended);
  const currentSelectedId = selectedActionId || recommendedAction?.id || problem.actions?.[0]?.id;

  return (
    <Dialog open={!!problem} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto bg-white">
        <DialogHeader className="pb-4 border-b border-gray-200">
          <div className="flex-1">
            <DialogTitle className="text-lg font-semibold text-gunmetal leading-snug pr-2 mb-2">
              {problem.title}
            </DialogTitle>
            <div className="flex items-center gap-3">
              <span className={cn('px-2.5 py-1 rounded-full text-xs font-semibold', config.bgClass, config.textClass)}>
                {config.label}
              </span>
              <span className="text-sm font-medium text-gunmetal">
                {formatAmount(cashAtRisk)} at risk
              </span>
            </div>
          </div>
        </DialogHeader>

        <div className="py-4 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gunmetal mb-3">What's Happening</h3>
          <ul className="space-y-2">
            {problem.context?.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-gunmetal/80">
                <span className="text-gunmetal/40 mt-0.5">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="py-4">
          <h3 className="text-sm font-semibold text-gunmetal mb-3">Your Options</h3>
          <div className="space-y-2">
            {problem.actions?.map((action) => (
              <div
                key={action.id}
                onClick={() => setSelectedActionId(action.id)}
                className={cn(
                  'p-4 rounded-lg border cursor-pointer transition-all',
                  currentSelectedId === action.id
                    ? 'bg-lime/10 border-lime/50 ring-2 ring-lime/20'
                    : 'bg-white border-gray-200 hover:border-gray-300'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm text-gunmetal">{action.title}</span>
                      {action.is_recommended && (
                        <span className="px-2 py-0.5 rounded-full bg-lime/20 text-lime-700 text-xs font-medium">
                          Recommended
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gunmetal/60">{action.description}</p>
                  </div>
                  <div className={cn(
                    'w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0',
                    currentSelectedId === action.id ? 'bg-lime border-lime' : 'border-gray-300'
                  )}>
                    {currentSelectedId === action.id && <Check className="w-3 h-3 text-white" />}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="pt-4 border-t border-gray-200 flex gap-3">
          <Button variant="outline" onClick={onDismiss} className="px-4 h-10 text-sm font-medium rounded-lg border-gray-200">
            <BellOff className="w-4 h-4 mr-1.5" />
            Dismiss
          </Button>
          <div className="relative">
            <Button variant="outline" onClick={() => setSnoozeOpen(!snoozeOpen)} className="px-4 h-10 text-sm font-medium rounded-lg border-gray-200">
              <Bell className="w-4 h-4 mr-1.5" />
              Snooze
            </Button>
            {snoozeOpen && (
              <div className="absolute bottom-full left-0 mb-2 p-2 bg-white rounded-lg shadow-lg border border-gray-200 min-w-[120px]">
                {[1, 3, 7].map(days => (
                  <button
                    key={days}
                    onClick={() => { onSnooze(days); setSnoozeOpen(false); }}
                    className="w-full px-3 py-1.5 text-sm text-left hover:bg-gray-50 rounded"
                  >
                    {days} day{days > 1 ? 's' : ''}
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button
            onClick={() => currentSelectedId && onApprove(currentSelectedId)}
            disabled={loadingActionId === currentSelectedId || !currentSelectedId}
            className="flex-1 h-10 bg-lime hover:bg-lime/90 text-gunmetal text-sm font-medium rounded-lg"
          >
            {loadingActionId === currentSelectedId ? (
              <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
            ) : (
              <Check className="w-4 h-4 mr-1.5" />
            )}
            Approve Selected
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Prepared Action Detail Modal (V1 Constraints)
// ============================================================================

interface PreparedActionDetailModalProps {
  action: PreparedActionSummary | null;
  onClose: () => void;
  onApprove: (actionId: string) => void;
}

function PreparedActionDetailModal({ action, onClose, onApprove }: PreparedActionDetailModalProps) {
  if (!action) return null;

  return (
    <Dialog open={!!action} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto bg-white">
        <DialogHeader className="pb-4 border-b border-gray-200">
          <div className="flex-1">
            <DialogTitle className="text-lg font-semibold text-gunmetal leading-snug pr-2 mb-2">
              {action.title}
            </DialogTitle>
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-lime/20 text-lime-700">
                Ready to execute
              </span>
              <span className="text-sm font-medium text-lime-600">
                Impact: {action.impact}
              </span>
            </div>
          </div>
        </DialogHeader>

        {/* Why This Matters */}
        {action.whyItMatters && (
          <div className="py-4 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gunmetal mb-2">Why This Matters</h3>
            <p className="text-sm text-gunmetal/80">{action.whyItMatters}</p>
          </div>
        )}

        {/* What Happens Next - V1 Constraints */}
        <div className="py-4 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gunmetal mb-4">What Happens Next</h3>

          {/* Tamio Handles */}
          {action.tamioHandles && action.tamioHandles.length > 0 && (
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-5 h-5 rounded-full bg-lime/20 flex items-center justify-center">
                  <Check className="w-3 h-3 text-lime-700" />
                </div>
                <span className="text-xs font-semibold uppercase tracking-wide text-lime-700">Tamio Handles</span>
              </div>
              <ul className="space-y-1.5 pl-7">
                {action.tamioHandles.map((item, idx) => (
                  <li key={idx} className="text-sm text-gunmetal/80 flex items-start gap-2">
                    <span className="text-lime-500 mt-0.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* User Handles */}
          {action.userHandles && action.userHandles.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-5 h-5 rounded-full bg-blue-100 flex items-center justify-center">
                  <User className="w-3 h-3 text-blue-600" />
                </div>
                <span className="text-xs font-semibold uppercase tracking-wide text-blue-600">You Handle</span>
              </div>
              <ul className="space-y-1.5 pl-7">
                {action.userHandles.map((item, idx) => (
                  <li key={idx} className="text-sm text-gunmetal/80 flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Description */}
        <div className="py-4">
          <h3 className="text-sm font-semibold text-gunmetal mb-2">Details</h3>
          <p className="text-sm text-gunmetal/70">{action.description}</p>
        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-gray-200 flex gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            className="px-4 h-10 text-sm font-medium rounded-lg border-gray-200"
          >
            Close
          </Button>
          <Button
            onClick={() => {
              onApprove(action.id);
              onClose();
            }}
            className="flex-1 h-10 bg-lime hover:bg-lime/90 text-gunmetal text-sm font-medium rounded-lg"
          >
            <Check className="w-4 h-4 mr-1.5" />
            Approve Action
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function Home() {
  const { user } = useAuth();

  // TAMI Chat state
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Data state
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [cashPosition, setCashPosition] = useState<CashPositionResponse | null>(null);
  const [rules, setRules] = useState<FinancialRule[]>([]);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [controlsData, setControlsData] = useState<Control[]>([]);
  const [queueCounts, setQueueCounts] = useState<ActionQueueResponse | null>(null);
  const [agentActivityData, setAgentActivityData] = useState<AgentActivityStats | null>(null);
  const [isDataLoading, setIsDataLoading] = useState(true);

  // UI state
  const [selectedProblem, setSelectedProblem] = useState<Problem | null>(null);
  const [selectedPreparedAction, setSelectedPreparedAction] = useState<PreparedActionSummary | null>(null);
  const [loadingActionId, setLoadingActionId] = useState<string | null>(null);
  const [isTamiExpanded, setIsTamiExpanded] = useState(false);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (scrollAreaRef.current) {
      const viewport = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [messages]);

  // Fetch data - uses same data source as Alerts & Actions page (getRisks/getControls)
  const fetchData = useCallback(async () => {
    if (!user) return;

    try {
      setIsDataLoading(true);

      const [forecastData, cashData, rulesData, risksData, controlsResponse, queueData, activityData] = await Promise.all([
        getForecast(user.id).catch(() => null),
        getCashPosition(user.id).catch(() => null),
        getRules(user.id).catch(() => []),
        getRisks().catch(() => ({ risks: [], total_count: 0 })),
        getControls().catch(() => ({ controls: [], total_count: 0 })),
        getActionQueueCounts().catch(() => null),
        getAgentActivity(24).catch(() => null),
      ]);

      setForecast(forecastData);
      setCashPosition(cashData);
      setRules(rulesData);

      // Store raw controls data for prepared actions
      const controls = controlsResponse.controls || [];
      setControlsData(controls);

      // Transform risks to problems format for the alerts section
      // Build a map of control IDs to controls for quick lookup
      const controlMap = new Map(controls.map(c => [c.id, c]));

      const risks = risksData.risks || [];
      if (risks.length > 0) {
        const transformedProblems = risks.map(risk => {
          // Find linked controls for this risk
          const linkedControls = (risk.linked_control_ids || [])
            .map(id => controlMap.get(id))
            .filter((c): c is Control => c !== undefined);
          return transformRiskToProblem(risk, linkedControls);
        });
        setProblems(transformedProblems);
      } else {
        // Fallback to mock data if no risks found
        setProblems(MOCK_PROBLEMS);
      }

      setQueueCounts(queueData);
      setAgentActivityData(activityData);
    } catch (err) {
      console.error('Failed to fetch data:', err);
      setProblems(MOCK_PROBLEMS);
      setControlsData([]);
    } finally {
      setIsDataLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Calculate KPIs
  const availableCash = parseFloat(cashPosition?.total_starting_cash || '0');
  const totalCashOut = forecast?.summary?.total_cash_out ? parseFloat(forecast.summary.total_cash_out) : 0;
  const monthlyExpenses = totalCashOut / 3;

  // Use backend-calculated runway weeks
  const runwayWeeks = forecast?.summary?.runway_weeks ?? 99;

  // Determine runway health status based on weeks
  const runwayStatus: { label: string; color: string } =
    runwayWeeks >= 26 ? { label: 'Healthy buffer', color: 'text-lime-600' } :
    runwayWeeks >= 12 ? { label: 'Moderate buffer', color: 'text-yellow-600' } :
    runwayWeeks >= 4 ? { label: 'Low buffer', color: 'text-orange-600' } :
    { label: 'Critical', color: 'text-tomato' };

  const bufferRule = rules.find((r) => r.rule_type === 'minimum_cash_buffer');
  const targetBufferMonths = (bufferRule?.threshold_config as { months?: number })?.months || 3;
  const lowestBalance = forecast?.summary?.lowest_cash_amount
    ? parseFloat(forecast.summary.lowest_cash_amount)
    : availableCash;
  const bufferCoverageMonths = monthlyExpenses > 0 ? Math.max(0, lowestBalance / monthlyExpenses) : lowestBalance > 0 ? 99 : 0;
  const bufferStatus: 'Safe' | 'At Risk' | 'Urgent' = bufferCoverageMonths < 1 ? 'Urgent' :
    bufferCoverageMonths < targetBufferMonths ? 'At Risk' : 'Safe';

  // Filter to urgent alerts only (severity = 'urgent' or due within 48 hours)
  // Sort by severity: urgent first, then high, then normal
  const urgentAlerts = useMemo(() => {
    const now = new Date();
    const severityOrder: Record<string, number> = { urgent: 0, high: 1, normal: 2 };

    return [...problems]
      .filter((problem) => {
        // Include if severity is urgent
        if (problem.severity === 'urgent') return true;

        // Include if detected recently and high severity (proxy for due soon)
        if (problem.severity === 'high') {
          const detectedAt = new Date(problem.detected_at);
          // Consider high priority items detected in last 48 hours as urgent
          return detectedAt >= new Date(now.getTime() - 48 * 60 * 60 * 1000);
        }

        return false;
      })
      .sort((a, b) => {
        const orderA = severityOrder[a.severity] ?? 2;
        const orderB = severityOrder[b.severity] ?? 2;
        // Primary sort by severity (urgent=0 comes first)
        if (orderA !== orderB) return orderA - orderB;
        // Secondary sort by detected_at (most recent first)
        return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
      })
      .slice(0, 5); // Limit to 5 urgent alerts
  }, [problems]);

  // Get top 3 urgent problems for contextual quick actions
  const urgentProblems = useMemo(() => {
    const severityOrder: Record<string, number> = { urgent: 0, high: 1, normal: 2 };
    return [...problems]
      .sort((a, b) => {
        const orderA = severityOrder[a.severity] ?? 2;
        const orderB = severityOrder[b.severity] ?? 2;
        if (orderA !== orderB) return orderA - orderB;
        return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
      })
      .slice(0, 3);
  }, [problems]);

  // Generate contextual quick actions from urgent problems (max 3)
  const contextualQuickActions = useMemo(() => {
    return urgentProblems.slice(0, 3).map(problem => ({
      text: generateContextualQuestion(problem),
      problemId: problem.id,
      severity: problem.severity,
    }));
  }, [urgentProblems]);

  // Check if a message is asking about position/cash/forecast
  const isPositionQuestion = (text: string): boolean => {
    const lowerText = text.toLowerCase();
    return lowerText.includes('position') ||
           lowerText.includes('cash') ||
           lowerText.includes('runway') ||
           lowerText.includes('buffer') ||
           lowerText.includes('how much') ||
           lowerText.includes('balance');
  };

  // Chat handlers
  const handleSend = async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text || !user) return;

    // Check if this is a position question to show inline cards
    const shouldShowInlineCards = isPositionQuestion(text);

    const userMessage: DisplayMessage = {
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const streamingMessage: DisplayMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      showInlineCards: shouldShowInlineCards,
    };
    setMessages((prev) => [...prev, streamingMessage]);

    const conversationHistory = formatConversationHistory(
      messages.map((m) => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      }))
    );

    await sendChatMessageStreaming(
      {
        user_id: user.id,
        message: text,
        conversation_history: conversationHistory,
        active_scenario_id: activeScenarioId,
      },
      (chunk) => {
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
            return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content + chunk }];
          }
          return prev;
        });
      },
      (event) => {
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              {
                ...lastMsg,
                isStreaming: false,
                mode: event.mode,
                suggestedActions: event.ui_hints?.suggested_actions,
                showScenarioBanner: event.ui_hints?.show_scenario_banner,
              }
            ];
          }
          return prev;
        });

        if (event.mode === 'build_scenario') {
          const scenarioId = (event.context_summary as Record<string, string | undefined>)?.active_scenario_id;
          if (scenarioId) {
            setActiveScenarioId(scenarioId);
          }
        }

        setIsLoading(false);
        inputRef.current?.focus();
      },
      (error) => {
        console.error('Streaming error:', error);
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
            return [
              ...prev.slice(0, -1),
              {
                ...lastMsg,
                content: 'I encountered an error processing your request. Please try again.',
                isStreaming: false,
                mode: 'clarify' as const,
              }
            ];
          }
          return prev;
        });
        setIsLoading(false);
        inputRef.current?.focus();
      }
    );
  };

  const handleActionClick = async (action: SuggestedAction) => {
    if (action.action === 'none') return;
    if (action.action === 'call_tool') {
      if (action.tool_name && action.tool_args && Object.keys(action.tool_args).length > 0) {
        const toolMessage = `[Action: ${action.label}] Please execute: ${action.tool_name} with parameters: ${JSON.stringify(action.tool_args)}`;
        await handleSend(toolMessage);
      } else {
        await handleSend(action.label);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const getModeLabel = (mode?: ChatMode): string => {
    switch (mode) {
      case 'explain_forecast': return 'Explaining';
      case 'suggest_scenarios': return 'Suggesting';
      case 'build_scenario': return 'Building Scenario';
      case 'goal_planning': return 'Planning';
      case 'clarify': return 'Clarifying';
      default: return '';
    }
  };

  // Problem handlers - use V4 alerts-actions API
  const handleApproveAction = async (actionId: string) => {
    setLoadingActionId(actionId);
    try {
      // Use V4 API to approve control
      await approveControl(actionId);
      toast.success('Action approved and queued for execution');
      setSelectedProblem(null);
      fetchData();
    } catch (err) {
      console.error('Failed to approve action:', err);
      // Fallback to legacy API if V4 fails
      try {
        await approveActionOption(actionId);
        toast.success('Action approved and queued for execution');
        setSelectedProblem(null);
        fetchData();
      } catch {
        toast.error('Failed to approve action');
      }
    } finally {
      setLoadingActionId(null);
    }
  };

  const handleDismissProblem = async () => {
    if (!selectedProblem) return;
    try {
      // Use V4 API to dismiss risk
      await dismissRisk(selectedProblem.id);
      setProblems(prev => prev.filter(p => p.id !== selectedProblem.id));
      setSelectedProblem(null);
      toast.success('Alert dismissed');
    } catch (err) {
      console.error('Failed to dismiss alert:', err);
      // Fallback to legacy API if V4 fails
      try {
        await dismissProblem(selectedProblem.id);
        setProblems(prev => prev.filter(p => p.id !== selectedProblem.id));
        setSelectedProblem(null);
        toast.success('Alert dismissed');
      } catch {
        toast.error('Failed to dismiss alert');
      }
    }
  };

  const handleSnoozeProblem = async (days: number) => {
    if (!selectedProblem) return;
    setProblems(prev => prev.filter(p => p.id !== selectedProblem.id));
    setSelectedProblem(null);
    toast.success(`Alert snoozed for ${days} day${days > 1 ? 's' : ''}`);
  };

  // Prepared action handler - use V4 API
  const handleApprovePreparedAction = async (actionId: string) => {
    try {
      await approveControl(actionId);
      toast.success('Action approved! Follow the steps shown to complete it.');
      setSelectedPreparedAction(null);
      fetchData();
    } catch (err) {
      console.error('Failed to approve action:', err);
      toast.error('Failed to approve action');
    }
  };

  // Mock prepared actions - these are ACTIONABLE items that mitigate risks from alerts
  const MOCK_PREPARED_ACTIONS: PreparedActionSummary[] = [
    {
      id: 'prep-1',
      title: 'Sweep $18.4K VAT to reserve account',
      description: 'Move accumulated VAT from last month\'s client payments to your tax reserve. Prevents accidental spending of funds owed to HMRC.',
      impact: '-$18K',
      impactAmount: -18400,
      status: 'pending',
      whyItMatters: 'You\'ve collected $92K in client payments this month. 20% ($18.4K) is VAT that needs to be set aside before your Q1 filing deadline.',
      tamioHandles: [
        'Calculated VAT from all client invoices',
        'Prepared transfer to tax reserve account',
        'Will update forecast to reflect reserved funds',
      ],
      userHandles: [
        'Approve the transfer',
        'Confirm in your banking app',
      ],
    },
    {
      id: 'prep-2',
      title: 'Send payment reminder to RetailCo',
      description: 'Draft email ready to send for overdue $52,500 invoice. Personalized based on your communication history with Sarah.',
      impact: '+$53K',
      impactAmount: 52500,
      status: 'pending',
      whyItMatters: 'Collecting this payment resolves your upcoming payroll shortfall and restores 3 weeks of runway.',
      tamioHandles: [
        'Drafted personalized follow-up email',
        'Analyzed their payment history (usually pays in 7 days)',
        'Will auto-update forecast when payment received',
      ],
      userHandles: [
        'Review and send the email',
        'Consider a quick phone call if no response in 48h',
      ],
    },
    {
      id: 'prep-3',
      title: 'Defer AWS payment by 15 days',
      description: 'Request payment extension on $8,200 AWS bill to align with expected RetailCo payment. Draft request prepared.',
      impact: '+$8K',
      impactAmount: 8200,
      status: 'pending',
      whyItMatters: 'Shifting this payment date prevents a cash crunch next week and keeps your buffer above the safety threshold.',
      tamioHandles: [
        'Identified payment timing conflict',
        'Drafted extension request email',
        'Calculated optimal deferral period',
      ],
      userHandles: [
        'Send request to AWS billing',
        'Update payment date if approved',
      ],
    },
    {
      id: 'prep-4',
      title: 'Schedule HealthTech Phase 2 call',
      description: 'Phase 1 ends in 3 weeks. Calendar invite drafted for Phase 2 scoping discussion to secure the $18K follow-on.',
      impact: '+$18K',
      impactAmount: 18000,
      status: 'pending',
      whyItMatters: 'Proactive outreach increases Phase 2 close rate by 40%. Early scheduling shows commitment and locks in their budget cycle.',
      tamioHandles: [
        'Identified contract end date approaching',
        'Drafted meeting invite with agenda',
        'Prepared Phase 2 proposal outline',
      ],
      userHandles: [
        'Review and send calendar invite',
        'Prepare talking points for the call',
      ],
    },
    {
      id: 'prep-5',
      title: 'Reduce Figma seats from 12 to 8',
      description: 'Analysis shows 4 unused seats. Downgrading before renewal saves $1,400/year. Cancellation request drafted.',
      impact: '-$1.4K',
      impactAmount: -1400,
      status: 'in_progress',
      whyItMatters: 'Auto-renewal in 12 days. Acting now captures the savings for the next billing cycle.',
      tamioHandles: [
        'Analyzed seat utilization (8/12 active)',
        'Identified inactive users',
        'Drafted downgrade request',
      ],
      userHandles: [
        'Confirm with team leads',
        'Submit change via Figma admin',
      ],
    },
  ];

  // Prepared actions - transform controls data or use mock fallback
  // Filter to show pending/active controls (not completed) and limit to 5
  const preparedActions: PreparedActionSummary[] = useMemo(() => {
    if (controlsData.length > 0) {
      return controlsData
        .filter(c => c.state === 'pending' || c.state === 'active')
        .slice(0, 5)
        .map(transformControlToPreparedAction);
    }
    return MOCK_PREPARED_ACTIONS;
  }, [controlsData]);

  // Demo agent list for hover tooltip
  const DEMO_AGENT_LIST = [
    'Cash Monitor',
    'Invoice Scanner',
    'Forecast Engine',
    'Obligation Tracker',
    'Scenario Simulator',
    'Alert Generator',
  ];

  // Agent activity stats - use real data or demo defaults
  const agentActivity = useMemo(() => ({
    simulationsRun: agentActivityData?.simulations_run ?? 147,
    invoicesScanned: agentActivityData?.invoices_scanned ?? 23,
    forecastsUpdated: agentActivityData?.forecasts_updated ?? 12,
    activeAgents: agentActivityData?.active_agents ?? 6,
    agentList: DEMO_AGENT_LIST,
  }), [agentActivityData]);

  // Suggested questions for TAMI (no emojis - brand aligned)
  const suggestedQuestions = useMemo(() => [
    'What happens if RetailCo pays 30 days late?',
    'Show me our 13-week cash forecast',
    'Can we afford to hire 2 people next month?',
    'Why is my buffer status at risk?',
  ], []);

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-7rem)] overflow-y-auto pb-4">
      {activeScenarioId && (
        <div className="absolute top-4 right-4 z-10">
          <Badge variant="outline" className="border-lime text-foreground bg-lime/10">
            <AlertTriangle className="h-3 w-3 mr-1" />
            Scenario Mode
          </Badge>
        </div>
      )}

      {/* Section 1: Quick Metrics (3-column) */}
      <div className="grid grid-cols-3 gap-4 flex-shrink-0">
        {/* Cash Position */}
        <NeuroCard className="p-6 text-center">
          <div className="text-3xl font-bold text-gray-900 mb-1">
            {isDataLoading ? '...' : formatCompactAmount(availableCash)}
          </div>
          <div className="text-sm text-gray-500 mb-2">Cash Position</div>
          <div className="text-xs text-tomato font-medium">
            <TrendingDown className="w-3 h-3 inline mr-1" />
            -4.0% (30D)
          </div>
        </NeuroCard>

        {/* Runway */}
        <NeuroCard className="p-6 text-center">
          <div className="text-3xl font-bold text-gray-900 mb-1">
            {isDataLoading ? '...' : `${runwayWeeks > 52 ? '52+' : runwayWeeks}w`}
          </div>
          <div className="text-sm text-gray-500 mb-2">Runway</div>
          <div className={cn('text-xs font-medium', runwayStatus.color)}>{runwayStatus.label}</div>
        </NeuroCard>

        {/* Buffer Status */}
        <NeuroCard className="p-6 text-center">
          <div className="flex items-center justify-center gap-2 mb-1">
            {!isDataLoading && (
              <>
                <div className={cn(
                  'w-2.5 h-2.5 rounded-full',
                  bufferStatus === 'Safe' ? 'bg-lime-500' :
                  bufferStatus === 'At Risk' ? 'bg-yellow-500' : 'bg-tomato'
                )} />
                <span className={cn(
                  'text-3xl font-bold',
                  bufferStatus === 'Safe' ? 'text-lime-700' :
                  bufferStatus === 'At Risk' ? 'text-yellow-700' : 'text-tomato'
                )}>
                  {bufferStatus === 'At Risk' ? 'Risk' : bufferStatus}
                </span>
              </>
            )}
            {isDataLoading && <span className="text-3xl font-bold">...</span>}
          </div>
          <div className="text-sm text-gray-500 mb-2">Buffer Status</div>
          <div className={cn(
            'text-xs font-medium',
            bufferStatus === 'Safe' ? 'text-lime-600' :
            bufferStatus === 'At Risk' ? 'text-tomato' : 'text-tomato'
          )}>
            {bufferStatus === 'At Risk' ? 'Below target by 2w' : 'On target'}
          </div>
        </NeuroCard>
      </div>

      {/* Section 2: Two-column grid - Alerts & Actions | Prepared Actions */}
      <div className="grid grid-cols-2 gap-4 flex-shrink-0">
        {/* Left: Urgent Alerts */}
        <NeuroCard className="p-0 overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-gray-100">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-base font-semibold text-gunmetal">Urgent Alerts</h3>
              <Badge className="bg-tomato/10 text-tomato border-0 text-xs font-medium">
                {urgentAlerts.length} urgent
              </Badge>
            </div>
            <p className="text-xs text-gray-500">Requiring action in the next 48 hours</p>
          </div>
          <div className="p-4 space-y-3 max-h-[320px] overflow-y-auto flex-1">
            {urgentAlerts.length === 0 ? (
              <div className="py-8 text-center">
                <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-lime/20 flex items-center justify-center">
                  <Check className="w-5 h-5 text-lime-700" />
                </div>
                <p className="text-sm font-medium text-gunmetal/60">No urgent alerts!</p>
                <p className="text-xs text-gray-400 mt-1">All items are on track</p>
              </div>
            ) : (
              urgentAlerts.map(problem => {
                const severity = (problem.severity as Severity) || 'normal';
                const tintClass = severity === 'urgent' ? 'alert-tint-urgent' :
                                  severity === 'high' ? 'alert-tint-high' : 'alert-tint-normal';

                return (
                  <div
                    key={problem.id}
                    className={cn(
                      'p-4 rounded-xl transition-all duration-200 hover:shadow-md',
                      tintClass
                    )}
                  >
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <h4 className="font-semibold text-sm text-gunmetal leading-snug line-clamp-2">
                        {problem.title}
                      </h4>
                      <SeverityPill severity={severity} />
                    </div>
                    <p className="text-xs text-gray-500 mb-3 line-clamp-2">
                      {problem.context?.[0] || 'Review and take action on this alert.'}
                    </p>
                    <div className="flex items-center justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs text-gray-500 hover:text-gunmetal hover:bg-transparent"
                        onClick={() => setSelectedProblem(problem)}
                      >
                        View details
                        <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
          {/* View All Alerts link */}
          <div className="px-4 pb-4 mt-auto">
            <Button
              variant="ghost"
              className="w-full text-sm text-gunmetal/60 hover:text-gunmetal flex items-center justify-center gap-1"
              onClick={() => window.location.href = '/action-monitor'}
            >
              View All Alerts ({queueCounts?.total_count ?? problems.length})
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </NeuroCard>

        {/* Right: Ready Actions */}
        <NeuroCard className="p-0 overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-gray-100">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-base font-semibold text-gunmetal">Ready Actions</h3>
              <Badge className="bg-lime/20 text-lime-700 border-0 text-xs font-medium">
                {preparedActions.length} pending
              </Badge>
            </div>
            <p className="text-xs text-gray-500">Awaiting your approval</p>
          </div>
          <div className="p-4 space-y-3 max-h-[320px] overflow-y-auto flex-1">
            {preparedActions.length === 0 ? (
              <div className="py-8 text-center">
                <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-lime/20 flex items-center justify-center">
                  <Check className="w-5 h-5 text-lime-700" />
                </div>
                <p className="text-sm font-medium text-gunmetal/60">No pending actions</p>
                <p className="text-xs text-gray-400 mt-1">All actions have been processed</p>
              </div>
            ) : (
              preparedActions.slice(0, 5).map(action => (
                <div key={action.id} className="p-4 rounded-xl action-tint transition-all duration-200 hover:shadow-md">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <h4 className="font-semibold text-sm text-gunmetal leading-snug line-clamp-2">
                      {action.title}
                    </h4>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                        action.impactAmount !== undefined && action.impactAmount < 0
                          ? 'bg-tomato/10 text-tomato border-tomato/20'
                          : 'bg-lime/10 text-lime-700 border-lime/20'
                      }`}>
                        {action.impact}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mb-3 line-clamp-2">
                    {action.description}
                  </p>
                  <div className="flex items-center justify-between">
                    <StatusPill status={action.status} />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs text-gray-500 hover:text-gunmetal hover:bg-transparent"
                      onClick={() => setSelectedPreparedAction(action)}
                    >
                      View details
                      <ArrowRight className="w-3 h-3 ml-1" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
          {/* View All Actions link */}
          <div className="px-4 pb-4 mt-auto">
            <Button
              variant="ghost"
              className="w-full text-sm text-gunmetal/60 hover:text-gunmetal flex items-center justify-center gap-1"
              onClick={() => window.location.href = '/action-monitor'}
            >
              View All Actions ({preparedActions.length})
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </NeuroCard>
      </div>

      {/* Section 3: Agent Activity (Compact) */}
      <NeuroCard className="p-4 flex-shrink-0">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gunmetal">Agent Activity (Last 24h)</h3>
          <div className="relative group">
            <Badge className="bg-lime/20 text-lime-700 border-0 text-xs font-medium cursor-default">
              {agentActivity.activeAgents} active
            </Badge>
            {/* Hover tooltip showing agent list */}
            <div className="absolute right-0 top-full mt-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-10">
              <div className="bg-gunmetal/95 backdrop-blur-sm rounded-lg py-2 px-3 shadow-lg min-w-[160px]">
                <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1.5">Active Agents</p>
                <ul className="space-y-1">
                  {agentActivity.agentList.map((agent, idx) => (
                    <li key={idx} className="flex items-center gap-2 text-xs text-white/90">
                      <span className="w-1.5 h-1.5 rounded-full bg-lime animate-pulse" />
                      {agent}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-gunmetal">{agentActivity.simulationsRun}</div>
            <div className="text-xs text-gray-500">Simulations run</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gunmetal">{agentActivity.invoicesScanned}</div>
            <div className="text-xs text-gray-500">Invoices scanned</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gunmetal">{agentActivity.forecastsUpdated}</div>
            <div className="text-xs text-gray-500">Forecasts updated</div>
          </div>
        </div>
      </NeuroCard>

      {/* Section 4: TAMI Chat (Enlarged) */}
      <NeuroCard className="flex-1 flex flex-col min-h-[400px] p-0 overflow-hidden">
        {messages.length === 0 ? (
          /* Empty state with suggested questions */
          <div className="flex-1 flex flex-col p-6">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="font-semibold text-gunmetal text-lg">Ask Tami anything</h3>
                <p className="text-sm text-gray-500">Run scenarios, check forecasts, or explore your cash position</p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsTamiExpanded(true)}
                className="h-8 w-8 text-gray-400 hover:text-gunmetal flex-shrink-0"
              >
                <Expand className="w-4 h-4" />
              </Button>
            </div>

            {/* Suggested Questions Grid (2x2) - glassmorphic, no emojis */}
            <div className="grid grid-cols-2 gap-3 mt-6 mb-6">
              {suggestedQuestions.map((question, index) => (
                <button
                  key={index}
                  onClick={() => handleSend(question)}
                  className="group p-4 rounded-xl suggested-prompt text-left cursor-pointer"
                >
                  <p className="text-sm text-gunmetal/80 leading-relaxed group-hover:text-gunmetal transition-colors">{question}</p>
                </button>
              ))}
            </div>

            {/* Chat Input */}
            <div className="mt-auto">
              <div className="relative">
                <Input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about your cash, obligations, or scenarios..."
                  disabled={isLoading}
                  className="pr-14 h-14 rounded-xl bg-gray-50 border-gray-200 focus:border-lime focus:ring-lime/30 text-base"
                />
                <Button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || isLoading}
                  size="icon"
                  className="absolute right-2 top-1/2 -translate-y-1/2 h-10 w-10 rounded-xl bg-tomato hover:bg-tomato/90 transition-all"
                >
                  <ArrowRight className="h-5 w-5 text-white" />
                </Button>
              </div>
            </div>
          </div>
        ) : (
          /* Chat conversation view */
          <>
            {/* Conversation header with expand button */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100/50">
              <h3 className="font-medium text-sm text-gunmetal">Tami</h3>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsTamiExpanded(true)}
                className="h-7 w-7 text-gray-400 hover:text-gunmetal"
              >
                <Expand className="w-3.5 h-3.5" />
              </Button>
            </div>
            <NeuroCardContent className="flex-1 flex flex-col min-h-0 p-0">
              <ScrollArea className="flex-1 h-full" ref={scrollAreaRef}>
                <div className="p-4">
                  <div className="space-y-4">
                    {messages.map((message, index) => (
                      <div key={index}>
                        <div className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                          {message.role === 'assistant' && (
                            <Avatar className="h-8 w-8 flex-shrink-0">
                              <AvatarFallback className="bg-gradient-to-br from-tomato to-tomato/70 text-white font-bold">
                                T
                              </AvatarFallback>
                            </Avatar>
                          )}
                          <div className={`max-w-[85%] ${message.role === 'user' ? 'bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-3 shadow-sm' : 'space-y-2'}`}>
                            {message.role === 'assistant' && message.mode && !message.isStreaming && (
                              <div className="flex items-center gap-2 mb-2">
                                <Badge variant="secondary" className="text-xs px-2 py-0.5 bg-muted/80">
                                  {getModeLabel(message.mode)}
                                </Badge>
                              </div>
                            )}

                            {message.role === 'assistant' && message.showScenarioBanner && (
                              <div className="p-2 bg-lime/10 border border-lime/30 rounded-lg text-xs mb-2 flex items-center gap-2">
                                <AlertTriangle className="h-3.5 w-3.5 text-lime" />
                                <span className="font-medium">Scenario editing mode active</span>
                              </div>
                            )}

                            {/* Inline KPI Cards for position questions */}
                            {message.role === 'assistant' && message.showInlineCards && !message.isStreaming && (
                              <InlineKPICards
                                availableCash={availableCash}
                                runwayWeeks={runwayWeeks}
                                bufferStatus={bufferStatus}
                              />
                            )}

                            {message.role === 'assistant' ? (
                              message.isStreaming && message.content === '' ? (
                                <TypingIndicator />
                              ) : message.isStreaming ? (
                                // While streaming, use plain markdown for real-time display
                                <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:my-1.5 text-sm">
                                  <ReactMarkdown>{message.content}</ReactMarkdown>
                                </div>
                              ) : (
                                // After streaming complete, use structured response for better formatting
                                <StructuredResponse content={message.content} />
                              )
                            ) : (
                              <p className="leading-relaxed text-sm">{message.content}</p>
                            )}

                            {message.role === 'assistant' && !message.isStreaming && message.suggestedActions && message.suggestedActions.length > 0 && (
                              <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-border/50">
                                {message.suggestedActions.map((action, actionIndex) => (
                                  <Button
                                    key={actionIndex}
                                    variant={action.action === 'none' ? 'outline' : 'default'}
                                    size="sm"
                                    className={cn('text-xs h-8', action.action !== 'none' && 'bg-primary hover:bg-primary/90')}
                                    onClick={() => handleActionClick(action)}
                                  >
                                    {action.label}
                                  </Button>
                                ))}
                              </div>
                            )}
                          </div>
                          {message.role === 'user' && (
                            <Avatar className="h-8 w-8 border-2 border-muted flex-shrink-0">
                              <AvatarFallback className="bg-muted">
                                <User className="h-4 w-4" />
                              </AvatarFallback>
                            </Avatar>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </ScrollArea>
            </NeuroCardContent>

            {/* Contextual Quick Actions (below conversation) */}
            {contextualQuickActions.length > 0 && (
              <div className="px-4 py-2 border-t bg-gray-50/50">
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {contextualQuickActions.map((action, index) => (
                    <Button
                      key={index}
                      variant="ghost"
                      size="sm"
                      className="h-7 px-3 text-xs whitespace-nowrap flex-shrink-0 hover:bg-lime/10"
                      onClick={() => handleSend(action.text)}
                    >
                      {action.text}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Input Area */}
            <div className="p-4 border-t bg-card/50 backdrop-blur-sm">
              <div className="relative">
                <Input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about your cash, obligations, or scenarios..."
                  disabled={isLoading}
                  className="pr-14 h-12 rounded-xl bg-background border-muted-foreground/20 focus:border-lime focus:ring-lime/30"
                />
                <Button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || isLoading}
                  size="icon"
                  className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 rounded-lg bg-tomato hover:bg-tomato/90 transition-all"
                >
                  <ArrowRight className="h-4 w-4 text-white" />
                </Button>
              </div>
            </div>
          </>
        )}
      </NeuroCard>

      {/* Problem Detail Modal */}
      <ProblemDetailModal
        problem={selectedProblem}
        onClose={() => setSelectedProblem(null)}
        onApprove={handleApproveAction}
        onDismiss={handleDismissProblem}
        onSnooze={handleSnoozeProblem}
        loadingActionId={loadingActionId}
      />

      {/* Prepared Action Detail Modal */}
      <PreparedActionDetailModal
        action={selectedPreparedAction}
        onClose={() => setSelectedPreparedAction(null)}
        onApprove={handleApprovePreparedAction}
      />

      {/* Tami Expanded Modal */}
      <TamiExpandedModal
        isOpen={isTamiExpanded}
        onClose={() => setIsTamiExpanded(false)}
        messages={messages}
        input={input}
        setInput={setInput}
        onSend={handleSend}
        isLoading={isLoading}
        getModeLabel={getModeLabel}
        onActionClick={handleActionClick}
      />
    </div>
  );
}
