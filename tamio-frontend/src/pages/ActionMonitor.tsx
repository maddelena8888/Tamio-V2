/**
 * Action Monitor - V4 Architecture
 *
 * Two-section layout:
 * 1. Problem Carousel - Horizontal scrolling cards showing detected problems
 * 2. Action Kanban Board - Three columns: Queued | Executing | Completed
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertCircle,
  X,
  Check,
  FileText,
  Mail,
  CreditCard,
  ArrowRightLeft,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  RefreshCw,
  Loader2,
  Copy,
  Download,
  Clock,
  DollarSign,
  TrendingUp,
  RotateCw,
  Plus,
  AlertTriangle,
  Pencil,
  Bot,
  Eye,
  Zap,
  Calendar,
  PiggyBank,
  Activity,
  Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import {
  getProblemsToReview,
  getActions,
  createAction,
  updateActionStatus,
  approveActionOption,
  rejectActionOption,
  dismissProblem,
  markActionComplete,
  archiveCompletedActions,
  type Problem,
  type PreparedAction,
  type ActionOption,
  type KanbanStatus,
  type CreateActionRequest,
  type ActionStep,
  type LinkedAlert,
} from '@/lib/api/actionMonitor';

// ============================================================================
// Types & Interfaces
// ============================================================================

type Severity = 'urgent' | 'high' | 'normal';
type ActionType = 'email' | 'payment_batch' | 'transfer' | 'manual';

// ============================================================================
// Style Configurations
// ============================================================================

const severityConfig: Record<Severity, { label: string; bgClass: string; textClass: string; iconColor: string }> = {
  urgent: {
    label: 'Urgent',
    bgClass: 'bg-tomato/10',
    textClass: 'text-tomato',
    iconColor: 'text-tomato',
  },
  high: {
    label: 'High',
    bgClass: 'bg-yellow-500/10',
    textClass: 'text-yellow-700',
    iconColor: 'text-yellow-600',
  },
  normal: {
    label: 'Normal',
    bgClass: 'bg-lime/10',
    textClass: 'text-lime-700',
    iconColor: 'text-lime-600',
  },
};

const priorityBadgeStyles: Record<Severity, string> = {
  urgent: 'bg-tomato/10 text-tomato border border-tomato/30',
  high: 'bg-yellow-500/10 text-yellow-700 border border-yellow-500/30',
  normal: 'bg-lime/10 text-lime-700 border border-lime/30',
};

const riskBadgeStyles: Record<string, string> = {
  low: 'bg-lime/20 text-lime-700 border border-lime/30',
  medium: 'bg-yellow-500/10 text-yellow-700 border border-yellow-500/30',
  high: 'bg-tomato/10 text-tomato border border-tomato/30',
};

const actionTypeIcons: Record<ActionType, React.ReactNode> = {
  email: <Mail className="w-4 h-4" />,
  payment_batch: <CreditCard className="w-4 h-4" />,
  transfer: <ArrowRightLeft className="w-4 h-4" />,
  manual: <FileText className="w-4 h-4" />,
};

// ============================================================================
// Utility Functions
// ============================================================================

const formatAmount = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.abs(value));
};

const formatDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return 'Unknown';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

const getDueDateColorClass = (deadline: string | null | undefined): string => {
  if (!deadline) return 'text-gray-500';

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const lowerDeadline = deadline.toLowerCase();
  if (lowerDeadline.includes('overdue') || lowerDeadline.includes('yesterday')) {
    return 'text-tomato font-medium';
  }
  if (lowerDeadline.includes('today')) {
    return 'text-yellow-700 font-medium';
  }

  const dueDate = new Date(deadline);
  if (!isNaN(dueDate.getTime())) {
    dueDate.setHours(0, 0, 0, 0);
    const diffDays = Math.ceil((dueDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) return 'text-tomato font-medium';
    if (diffDays === 0) return 'text-yellow-700 font-medium';
  }

  return 'text-gray-500';
};

// ============================================================================
// Mock Data
// ============================================================================

// OBLIGATION-FOCUSED Mock Problems
// Alerts focus on obligations at risk, not on client payments
const MOCK_PROBLEMS: Problem[] = [
  {
    id: 'problem-1',
    title: 'Payroll underfunded by $8K - due Friday',
    severity: 'urgent',
    detected_at: new Date().toISOString(),
    trigger: 'Obligation Monitor Agent',
    context: [
      'Bi-weekly payroll of $85,000 is $8,000 short based on current cash',
      'Caused by: RetailCo payment $52,500 (14 days overdue)',
      'Current cash: $77K. Payroll requires: $85K',
    ],
    actions: [
      {
        id: 'action-1a',
        title: 'Chase RetailCo payment',
        description: 'Send firm reminder to collect $52,500 overdue payment',
        risk_level: 'medium',
        is_recommended: true,
        reasoning: ['Collecting $52.5K covers payroll shortfall', 'Client is 14 days overdue'],
        cash_impact: 52500,
        impact_description: 'Covers payroll + $44.5K buffer',
        prepared_content: {
          email_subject: 'Urgent: Payment Required - RetailCo Invoice',
          email_body: 'Dear RetailCo Team,\n\nWe hope this message finds you well. We wanted to follow up on the outstanding invoice.\n\nThe payment of $52,500 was due 14 days ago. We kindly request that you process this payment at your earliest convenience.\n\nBest regards,\nFinance Team',
          recipient: 'accounts@retailco.com',
        },
        status: 'pending',
        success_probability: 0.75,
      },
      {
        id: 'action-1b',
        title: 'Draw from credit line',
        description: 'Draw $8K from credit facility to cover shortfall',
        risk_level: 'low',
        is_recommended: false,
        reasoning: ['Immediate solution', 'Small interest cost ~$53/month'],
        cash_impact: 8000,
        impact_description: 'Covers shortfall immediately',
        prepared_content: { description: 'Credit line draw of $8,000 to cover payroll shortfall.' },
        status: 'pending',
        success_probability: 1.0,
      },
    ],
  },
  {
    id: 'problem-2',
    title: 'VAT payment at risk - due in 5 days',
    severity: 'high',
    detected_at: new Date(Date.now() - 86400000).toISOString(),
    trigger: 'Obligation Monitor Agent',
    context: [
      'Q1 VAT payment of $28,000 due in 5 days',
      'Current projected cash at due date: $24,500',
      'Caused by: TechCorp invoice $28K (3 days until due, not yet paid)',
    ],
    actions: [
      {
        id: 'action-2a',
        title: 'Send TechCorp reminder',
        description: 'Gentle reminder about upcoming invoice due date',
        risk_level: 'low',
        is_recommended: true,
        reasoning: ['Client has 95% on-time history', 'Collecting covers VAT fully'],
        cash_impact: 28000,
        impact_description: 'Covers VAT payment',
        prepared_content: {
          email_subject: 'Reminder: Invoice Due Soon',
          email_body: 'Hi TechCorp Team,\n\nJust a friendly reminder that your invoice is due in 3 days...',
        },
        status: 'pending',
        success_probability: 0.9,
      },
    ],
  },
  {
    id: 'problem-3',
    title: 'Office rent covered - confirm payment',
    severity: 'normal',
    detected_at: new Date(Date.now() - 172800000).toISOString(),
    trigger: 'Obligation Monitor Agent',
    context: [
      'Monthly office rent of $8,500 due on the 1st',
      'Cash is sufficient with healthy buffer',
      'Confirm to process on schedule',
    ],
    actions: [
      {
        id: 'action-3a',
        title: 'Confirm rent payment',
        description: 'Process rent payment as scheduled',
        risk_level: 'low',
        is_recommended: true,
        reasoning: ['Cash is sufficient', 'Maintains good standing with landlord'],
        cash_impact: -8500,
        impact_description: 'Scheduled fixed cost',
        prepared_content: { description: 'Rent payment confirmed for the 1st.' },
        status: 'pending',
        success_probability: 1.0,
      },
    ],
  },
  {
    id: 'problem-4',
    title: 'Q1 estimated taxes - due in 3 weeks',
    severity: 'normal',
    detected_at: new Date(Date.now() - 43200000).toISOString(),
    trigger: 'Tax Obligation Agent',
    context: [
      'Estimated Q1 tax payment of $42,000 due in 3 weeks',
      'Current projection shows sufficient funds',
      'Set aside reserves now to ensure coverage',
    ],
    actions: [
      {
        id: 'action-4a',
        title: 'Reserve tax funds',
        description: 'Earmark $42,000 for upcoming tax payment',
        risk_level: 'low',
        is_recommended: true,
        reasoning: ['Avoid late payment penalties', 'Maintain good standing with IRS'],
        cash_impact: -42000,
        impact_description: 'Tax obligation',
        prepared_content: { description: 'Q1 estimated tax payment reserved.' },
        status: 'pending',
        success_probability: 1.0,
      },
    ],
  },
];

// ============================================================================
// Agent Types and Data
// ============================================================================

interface Agent {
  id: string;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  category: 'core' | 'detection' | 'preparation';
  status: 'active' | 'inactive';
  purpose: string;
  intelligenceType: string;
  runFrequency: string;
  whatItDoes: string[];
  metrics: { label: string; value: string }[];
  accentColor: string;
}

const agents: Agent[] = [
  {
    id: 'forecast-engine',
    name: 'Forecast Engine',
    icon: Zap,
    category: 'core',
    status: 'active',
    purpose: 'Projects your 13-week cash position by analyzing all expected inflows and outflows, applying probability weights to uncertain revenue, and flagging weeks where you\'ll breach your buffer threshold.',
    intelligenceType: 'Hybrid (Rules + Statistical Models)',
    runFrequency: 'Real-time + every 6 hours',
    whatItDoes: [
      'Aggregates all cash flow data including bank balances, scheduled obligations, expected revenue, and recurring expenses',
      'Uses client payment patterns to adjust expected receipt dates',
      'Accounts for seasonal variations in revenue/expenses',
      'Applies confidence scores to uncertain inflows (80% likely vs. 50% likely)',
      'Flags weeks where ending balance drops below buffer threshold',
    ],
    metrics: [
      { label: 'Forecast Accuracy', value: '94%' },
      { label: 'Confidence Level', value: 'High' },
      { label: 'Buffer Status', value: 'Safe' },
      { label: 'Runway', value: '18 weeks' },
    ],
    accentColor: 'bg-blue-500/10 text-blue-600 border-blue-200',
  },
  {
    id: 'vigilance-agent',
    name: 'Cash Flow Vigilance Agent',
    icon: Eye,
    category: 'detection',
    status: 'active',
    purpose: 'Continuously monitors your cash position against upcoming obligations and buffer thresholds, detecting potential shortfalls before they become crises.',
    intelligenceType: 'Hybrid (Rules + Statistical Analysis)',
    runFrequency: 'Every 6 hours + event-driven',
    whatItDoes: [
      'Monitors buffer health and tracks daily bank balances vs. minimum buffer threshold',
      'Calculates days until buffer breach (forward-looking)',
      'Runs 7 days before each payroll date to check safety',
      'Flags payments delayed beyond normal range (7+ days late)',
      'Detects potential churn (revenue drop >20% from baseline)',
    ],
    metrics: [
      { label: 'Checks This Week', value: '28' },
      { label: 'Alerts Created', value: '3' },
      { label: 'Resolution Rate', value: '87%' },
      { label: 'Avg Lead Time', value: '5 days' },
    ],
    accentColor: 'bg-purple-500/10 text-purple-600 border-purple-200',
  },
  {
    id: 'ar-invoice-agent',
    name: 'AR & Invoice Agent',
    icon: FileText,
    category: 'preparation',
    status: 'active',
    purpose: 'Manages the full invoice lifecycle: calculates amounts owed, generates invoice drafts, and drafts collection emails for overdue payments with tone calibrated to client relationship strength.',
    intelligenceType: 'Hybrid (Rules + AI/LLM)',
    runFrequency: 'Daily at 9am + event-driven',
    whatItDoes: [
      'Triggers invoice generation when due date arrives (based on contract terms)',
      'Calculates amount owed: Retainer (fixed), Hourly (tracked hours × rate), Milestone (agreed amount)',
      'Generates invoice draft with correct line items, amounts, payment terms, and due date',
      'Detects overdue invoices (7+ days beyond due date)',
      'Generates collection email with calibrated tone based on relationship type',
    ],
    metrics: [
      { label: 'Invoices Generated', value: '12' },
      { label: 'Awaiting Review', value: '2' },
      { label: 'Collection Emails', value: '4' },
      { label: 'Success Rate', value: '78%' },
    ],
    accentColor: 'bg-amber-500/10 text-amber-600 border-amber-200',
  },
  {
    id: 'vendor-payment-agent',
    name: 'Vendor & Payment Agent',
    icon: CreditCard,
    category: 'preparation',
    status: 'active',
    purpose: 'When cash is tight, ranks vendors by delay risk and drafts postponement messages that preserve relationships while buying you time.',
    intelligenceType: 'Hybrid (Algorithm + AI/LLM)',
    runFrequency: 'Event-driven (shortfall detected)',
    whatItDoes: [
      'Triggered by payroll safety alert (red status) or buffer breach detection',
      'Analyzes all vendors with payments due in next 7-14 days',
      'Calculates composite risk score: payment terms remaining, operational criticality, past delay tolerance',
      'Ranks vendors from safest to riskiest to delay',
      'Generates vendor-specific delay message with professional tone',
    ],
    metrics: [
      { label: 'Delay Options', value: '6' },
      { label: 'Delays Executed', value: '2' },
      { label: 'Success Rate', value: '92%' },
      { label: 'Avg Delay', value: '5 days' },
    ],
    accentColor: 'bg-rose-500/10 text-rose-600 border-rose-200',
  },
  {
    id: 'batch-sequencer',
    name: 'Payment Batch Sequencer',
    icon: Calendar,
    category: 'preparation',
    status: 'active',
    purpose: 'Optimizes the timing and sequencing of vendor payments across the week to maintain healthy cash buffer while ensuring critical vendors are paid on time.',
    intelligenceType: 'Hybrid (Optimization Algorithm + Rules)',
    runFrequency: 'Weekly (Sunday 8pm) + mid-week',
    whatItDoes: [
      'Queries all bills due in upcoming week (next 7 days)',
      'Categorizes by criticality: Critical (payroll, utilities), Important (key vendors), Flexible (marketing)',
      'Simulates different payment schedules (Mon/Wed/Fri splits)',
      'Ensures buffer never drops below minimum threshold',
      'Generates CSV/ACH files for bank upload grouped by scheduled date',
    ],
    metrics: [
      { label: 'Batches Optimized', value: '4' },
      { label: 'Payments Sequenced', value: '23' },
      { label: 'Buffer Maintained', value: '100%' },
      { label: 'Critical On-Time', value: '100%' },
    ],
    accentColor: 'bg-teal-500/10 text-teal-600 border-teal-200',
  },
  {
    id: 'excess-allocator',
    name: 'Excess Cash Allocator',
    icon: PiggyBank,
    category: 'preparation',
    status: 'active',
    purpose: 'Identifies when operating cash exceeds buffer + near-term obligations and suggests optimal allocation strategies (tax reserves, savings, investments, or growth spending).',
    intelligenceType: 'Hybrid (Rules + AI/LLM)',
    runFrequency: 'Weekly + event-driven',
    whatItDoes: [
      'Monitors operating balance vs. buffer + 30-day obligations',
      'Triggers when excess cash exceeds configurable threshold',
      'Calculates optimal allocation based on tax obligations, savings goals, and growth priorities',
      'Generates allocation recommendations with reasoning',
      'Tracks allocation history and adjusts recommendations based on patterns',
    ],
    metrics: [
      { label: 'Excess Detected', value: '$24K' },
      { label: 'Allocations Made', value: '3' },
      { label: 'Tax Reserve', value: '$18K' },
      { label: 'Savings Rate', value: '12%' },
    ],
    accentColor: 'bg-emerald-500/10 text-emerald-600 border-emerald-200',
  },
];

const MOCK_ACTIONS: { queued: PreparedAction[]; executing: PreparedAction[]; completed: PreparedAction[] } = {
  queued: [
    {
      id: 'queued-1',
      title: 'Notify freelancer of payment delay',
      action_type: 'email',
      urgency: 'urgent',
      impact_amount: 4500,
      deadline: 'Due Today',
      problem_context: 'RetailCo payment delay affecting contractor payment schedule',
      is_recurring: false,
      draft_content: {
        email_subject: 'Payment timing update - January invoice',
        email_body: 'Hi Alex,\n\nDue to a client payment delay from RetailCo, we\'ll process your January invoice ($4,500) on Friday instead of Wednesday. This is a one-time adjustment.\n\nThanks for your understanding.\n\nBest,\nMaddy',
        recipient: 'alex@freelancedesign.com',
      },
      status: 'queued',
      is_system_generated: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      approved_at: 'Jan 10, 2026',
      linked_entity_name: 'Alex (Freelance Designer)',
      linked_entity_type: 'expense_bucket',
      action_steps: [
        { id: 'step-1', title: 'Draft notification email', owner: 'tamio', status: 'completed', order: 1 },
        { id: 'step-2', title: 'Review and send email', owner: 'user', status: 'pending', order: 2 },
        { id: 'step-3', title: 'Log communication', owner: 'tamio', status: 'pending', order: 3 },
      ],
      linked_alert: {
        id: 'alert-1',
        title: 'Cash Buffer Tight for Payroll',
        severity: 'urgent',
        detected_at: new Date(Date.now() - 172800000).toISOString(),
        cash_impact: -85000,
        context_summary: [
          'Bi-weekly payroll of $85,000 due Friday',
          'RetailCo payment ($52,500) still outstanding',
          'Delaying freelancer payment preserves $4,500 buffer',
        ],
      },
    },
    {
      id: 'queued-2',
      title: 'Send RetailCo payment reminder',
      action_type: 'email',
      urgency: 'high',
      impact_amount: 52500,
      deadline: 'Tomorrow',
      problem_context: 'Design milestone payment 14 days overdue',
      is_recurring: false,
      draft_content: {
        email_subject: 'Urgent: Outstanding Invoice - RetailCo Rebrand Project',
        email_body: 'Dear RetailCo Team,\n\nWe hope this message finds you well. We wanted to follow up on the outstanding invoice for the Design Milestone of the Rebrand project.\n\nThe payment of $52,500 was due 14 days ago upon completion of the design phase. We kindly request that you process this payment at your earliest convenience.\n\nIf you have any questions or need to discuss payment arrangements, please don\'t hesitate to reach out.\n\nBest regards,\nMaddy',
        recipient: 'accounts@retailco.com',
      },
      status: 'queued',
      is_system_generated: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      approved_at: 'Jan 9, 2026',
      linked_entity_name: 'RetailCo',
      linked_entity_type: 'client',
      action_steps: [
        { id: 'step-1', title: 'Draft payment reminder', owner: 'tamio', status: 'completed', order: 1 },
        { id: 'step-2', title: 'Review and send email', owner: 'user', status: 'pending', order: 2 },
        { id: 'step-3', title: 'Schedule follow-up call', owner: 'user', status: 'pending', order: 3 },
      ],
      linked_alert: {
        id: 'alert-2',
        title: 'Overdue Client Payment',
        severity: 'high',
        detected_at: new Date(Date.now() - 86400000).toISOString(),
        cash_impact: 52500,
        context_summary: [
          'Invoice #RC-2024-045 is 14 days overdue',
          'Client is transactional (5.5% of revenue)',
          'This delay is unusual - invoice was due on milestone completion',
        ],
      },
    },
    {
      id: 'queued-3',
      title: 'Schedule Q1 tax payment',
      action_type: 'payment_batch',
      urgency: 'normal',
      impact_amount: 18500,
      deadline: 'In 5 days',
      problem_context: 'Q1 2026 Estimated Tax Payment',
      is_recurring: true,
      draft_content: {
        description: 'Schedule Q1 2026 estimated tax payment of $18,500 to IRS.',
        payment_details: {
          amount: 18500,
          from_account: 'Operating Account',
          to: 'IRS - Estimated Tax',
          reference: 'Q1-2026-EST',
        },
      },
      status: 'queued',
      is_system_generated: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      linked_entity_name: 'Q1 Estimated Tax',
      linked_entity_type: 'expense_bucket',
      action_steps: [
        { id: 'step-1', title: 'Verify tax reserve balance', owner: 'user', status: 'pending', order: 1 },
        { id: 'step-2', title: 'Schedule IRS payment', owner: 'user', status: 'pending', order: 2 },
      ],
    },
  ],
  executing: [
    {
      id: 'executing-1',
      title: 'Process TechCorp retainer invoice',
      action_type: 'email',
      urgency: 'normal',
      impact_amount: 12000,
      deadline: 'In 2 days',
      problem_context: 'Monthly retainer invoice ready for TechCorp',
      is_recurring: true,
      draft_content: {
        email_subject: 'Invoice #TC-2026-001 - January Retainer',
        email_body: 'Hi TechCorp Team,\n\nPlease find attached your January retainer invoice (#TC-2026-001) for $12,000.\n\nPayment terms: Net 15\nDue date: January 25, 2026\n\nThank you for your continued partnership!\n\nBest,\nMaddy',
        recipient: 'ap@techcorp.com',
      },
      status: 'executing',
      is_system_generated: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      linked_entity_name: 'TechCorp',
      linked_entity_type: 'client',
      action_steps: [
        { id: 'step-1', title: 'Generate invoice PDF', owner: 'tamio', status: 'completed', order: 1 },
        { id: 'step-2', title: 'Review invoice details', owner: 'user', status: 'completed', order: 2 },
        { id: 'step-3', title: 'Send invoice email', owner: 'user', status: 'in_progress', order: 3 },
      ],
    },
  ],
  completed: [
    {
      id: 'completed-1',
      title: 'Sent StartupX renewal proposal',
      action_type: 'email',
      urgency: 'normal',
      impact_amount: 102000,
      deadline: null,
      problem_context: 'Annual contract renewal with upsell opportunity',
      is_recurring: false,
      draft_content: {
        email_subject: 'Your 2026 Partnership Renewal - Exclusive Offer',
        email_body: 'Hi StartupX Team,\n\nAs we approach your contract renewal date, I wanted to reach out personally to discuss your 2026 partnership...',
        recipient: 'ceo@startupx.com',
      },
      status: 'completed',
      is_system_generated: true,
      created_at: new Date(Date.now() - 172800000).toISOString(),
      updated_at: new Date(Date.now() - 86400000).toISOString(),
      completed_at: new Date(Date.now() - 86400000).toISOString(),
      linked_entity_name: 'StartupX',
      linked_entity_type: 'client',
      action_steps: [
        { id: 'step-1', title: 'Draft renewal proposal', owner: 'tamio', status: 'completed', order: 1 },
        { id: 'step-2', title: 'Review pricing tiers', owner: 'user', status: 'completed', order: 2 },
        { id: 'step-3', title: 'Send proposal email', owner: 'user', status: 'completed', order: 3 },
      ],
    },
    {
      id: 'completed-2',
      title: 'Paid AWS hosting invoice',
      action_type: 'payment_batch',
      urgency: 'normal',
      impact_amount: 2850,
      deadline: null,
      problem_context: 'Monthly hosting expense',
      is_recurring: true,
      draft_content: {
        description: 'Processed monthly AWS hosting payment of $2,850.',
      },
      status: 'completed',
      is_system_generated: true,
      created_at: new Date(Date.now() - 259200000).toISOString(),
      updated_at: new Date(Date.now() - 172800000).toISOString(),
      completed_at: new Date(Date.now() - 172800000).toISOString(),
      linked_entity_name: 'AWS Hosting',
      linked_entity_type: 'expense_bucket',
      action_steps: [
        { id: 'step-1', title: 'Review invoice amount', owner: 'user', status: 'completed', order: 1 },
        { id: 'step-2', title: 'Process payment', owner: 'user', status: 'completed', order: 2 },
      ],
    },
  ],
};

// ============================================================================
// Sub-Components
// ============================================================================

// Problem Card (Collapsed - for carousel)
interface ProblemCardProps {
  problem: Problem;
  onExpand: () => void;
  onDismiss: () => void;
}

function ProblemCard({ problem, onExpand, onDismiss }: ProblemCardProps) {
  const severity = (problem.severity as Severity) || 'normal';
  const config = severityConfig[severity];

  const pendingCount = problem.actions?.filter((a) => a.status === 'pending').length || 0;
  const approvedCount = problem.actions?.filter((a) => a.status === 'approved').length || 0;
  const rejectedCount = problem.actions?.filter((a) => a.status === 'rejected').length || 0;

  // Check if this alert originated from a forecast prediction
  // For demo purposes, we'll check if the trigger contains certain keywords
  const hasForecastConnection = problem.trigger?.toLowerCase().includes('forecast') ||
    problem.trigger?.toLowerCase().includes('monitor') ||
    problem.title?.toLowerCase().includes('payroll') ||
    problem.title?.toLowerCase().includes('vat');

  // Calculate days ago for forecast badge
  const detectedDate = new Date(problem.detected_at);
  const daysAgo = Math.floor((Date.now() - detectedDate.getTime()) / (1000 * 60 * 60 * 24));

  return (
    <div className="flex-shrink-0 w-[calc((100%-2rem)/3)] min-w-[280px]">
      <NeuroCard className="h-full p-4 flex flex-col">
        {/* Header row: urgency badge + dismiss */}
        <div className="flex items-center justify-between mb-3">
          <span className={cn(
            'px-3 py-1 rounded-full text-xs font-semibold',
            config.bgClass,
            config.textClass
          )}>
            {config.label}
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); onDismiss(); }}
            className="w-6 h-6 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label="Dismiss problem"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Title */}
        <h3 className="font-semibold text-sm leading-snug text-gunmetal mb-2 line-clamp-2">
          {problem.title}
        </h3>

        {/* Description (first context item) */}
        {problem.context && problem.context[0] && (
          <p className="text-xs text-gray-500 mb-2 line-clamp-2">
            {problem.context[0]}
          </p>
        )}

        {/* Detected timestamp */}
        <p className="text-xs text-gray-500 mb-2">
          Detected: {formatDateTime(problem.detected_at)}
        </p>

        {/* Status summary */}
        <div className="flex items-center gap-3 text-xs text-gray-500 mb-3">
          <span>{pendingCount} pending</span>
          <span className="w-1 h-1 rounded-full bg-gray-300" />
          <span>{approvedCount} approved</span>
          <span className="w-1 h-1 rounded-full bg-gray-300" />
          <span>{rejectedCount} rejected</span>
        </div>

        {/* Forecast connection badge */}
        {hasForecastConnection && (
          <a
            href={`/scenarios?week=${Math.min(daysAgo + 1, 13)}`}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1.5 px-2.5 py-1.5 mb-3 rounded-lg bg-blue-50 border border-blue-100 text-xs text-blue-600 hover:bg-blue-100 transition-colors"
          >
            <TrendingUp className="w-3 h-3" />
            <span>Predicted on Forecast {daysAgo > 0 ? `${daysAgo} days ago` : 'today'}</span>
            <ArrowRight className="w-3 h-3 ml-auto" />
          </a>
        )}

        {/* View details button - pushed to bottom */}
        <div className="mt-auto">
          <button
            onClick={onExpand}
            className="w-full py-2 rounded-lg bg-gray-50 hover:bg-gray-100 border border-gray-200 text-sm font-medium text-gunmetal flex items-center justify-center gap-1.5 transition-colors"
          >
            View Details
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </NeuroCard>
    </div>
  );
}

// Action Option Card (for Problem Modal)
interface ActionOptionCardProps {
  action: ActionOption;
  onApprove: () => void;
  onReject: () => void;
  onViewDraft: () => void;
  isLoading?: boolean;
}

function ActionOptionCard({ action, onApprove, onReject, onViewDraft, isLoading }: ActionOptionCardProps) {
  const riskStyle = riskBadgeStyles[action.risk_level] || riskBadgeStyles.medium;

  return (
    <div className="p-4 rounded-xl bg-white border border-gray-200">
      {/* Title + badges */}
      <div className="flex items-start justify-between mb-3">
        <h5 className="font-semibold text-sm text-gunmetal">
          {action.title}
          {action.cash_impact && ` ($${formatAmount(action.cash_impact)})`}
        </h5>
        <div className="flex gap-2 flex-shrink-0 ml-3">
          {action.is_recommended && (
            <span className="px-2 py-0.5 rounded-full bg-lime/20 text-lime-700 text-xs font-medium">
              Recommended
            </span>
          )}
          <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', riskStyle)}>
            {action.risk_level.charAt(0).toUpperCase() + action.risk_level.slice(1)} Risk
          </span>
        </div>
      </div>

      {/* Reasoning bullets */}
      <ul className="space-y-1 mb-3 text-sm text-gray-600">
        {action.reasoning?.map((reason, idx) => (
          <li key={idx} className="flex items-start gap-2">
            <span className="text-gray-400 mt-0.5">•</span>
            <span>{reason}</span>
          </li>
        ))}
        {action.impact_description && (
          <li className="flex items-start gap-2">
            <span className="text-gray-400 mt-0.5">•</span>
            <span>Impact: <span className="font-medium text-gunmetal">{action.impact_description}</span></span>
          </li>
        )}
      </ul>

      {/* Action buttons */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onViewDraft}
          className="px-3 py-1.5 h-8 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-medium"
          disabled={isLoading}
        >
          <FileText className="w-3.5 h-3.5 mr-1.5" />
          View Draft
        </Button>

        <Button
          size="sm"
          onClick={onApprove}
          disabled={action.status === 'approved' || isLoading}
          className="flex-1 px-3 py-1.5 h-8 rounded-lg bg-lime hover:bg-lime/90 text-gunmetal text-xs font-medium disabled:opacity-50"
        >
          {isLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Check className="w-3.5 h-3.5 mr-1.5" />}
          {action.status === 'approved' ? 'Approved' : 'Approve'}
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={onReject}
          disabled={action.status === 'rejected' || isLoading}
          className="px-3 py-1.5 h-8 rounded-lg border border-tomato bg-white hover:bg-tomato/5 text-tomato text-xs font-medium disabled:opacity-50"
        >
          <X className="w-3.5 h-3.5 mr-1.5" />
          Reject
        </Button>
      </div>
    </div>
  );
}

// Draggable Kanban Action Card
interface KanbanActionCardProps {
  action: PreparedAction;
  onClick: () => void;
  isDragging?: boolean;
}

function KanbanActionCard({ action, onClick, isDragging }: KanbanActionCardProps) {
  const urgency = (action.urgency as Severity) || 'normal';
  const actionType = (action.action_type as ActionType) || 'manual';
  const priorityStyle = priorityBadgeStyles[urgency];
  const dueDateColorClass = getDueDateColorClass(action.deadline);

  return (
    <NeuroCard
      onClick={onClick}
      className={cn(
        'p-3 cursor-pointer hover:shadow-lg transition-all',
        isDragging && 'opacity-50 shadow-xl'
      )}
    >
      {/* Top row: Priority badge and linked entity */}
      <div className="flex items-center justify-between mb-2">
        <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', priorityStyle)}>
          {urgency.charAt(0).toUpperCase() + urgency.slice(1)}
        </span>

        {action.linked_entity_name && (
          <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-xs font-medium">
            {action.linked_entity_name}
          </span>
        )}
      </div>

      {/* Action type icon + title */}
      <div className="flex items-start gap-2 mb-2">
        <div className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5">
          {actionTypeIcons[actionType] || actionTypeIcons.manual}
        </div>
        <h4 className="font-medium text-sm leading-snug text-gunmetal">
          {action.title}
        </h4>
      </div>

      {/* Metadata row */}
      <div className="flex items-center gap-2 text-xs text-gray-500">
        {action.impact_amount && (
          <>
            <div className="flex items-center gap-1">
              <DollarSign className="w-3 h-3" />
              <span>{formatAmount(action.impact_amount)}</span>
            </div>
            <span className="w-1 h-1 rounded-full bg-gray-300" />
          </>
        )}

        {action.deadline && (
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span className={dueDateColorClass}>{action.deadline}</span>
          </div>
        )}
      </div>

      {/* Problem context (if linked) */}
      {action.problem_context && (
        <div className="mt-2 pt-2 border-t border-gray-100">
          <div className="flex items-start gap-1.5 text-xs text-gray-500">
            <TrendingUp className="w-3 h-3 flex-shrink-0 mt-0.5" />
            <span className="line-clamp-1">{action.problem_context}</span>
          </div>
        </div>
      )}

      {/* Recurring badge (if applicable) */}
      {action.is_recurring && (
        <div className="mt-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 text-xs font-medium">
            <RotateCw className="w-2.5 h-2.5" />
            Recurring
          </span>
        </div>
      )}
    </NeuroCard>
  );
}

// Sortable wrapper for KanbanActionCard
interface SortableActionCardProps {
  action: PreparedAction;
  onClick: () => void;
}

function SortableActionCard({ action, onClick }: SortableActionCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: action.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <KanbanActionCard action={action} onClick={onClick} isDragging={isDragging} />
    </div>
  );
}

// Kanban Column
interface KanbanColumnProps {
  title: string;
  columnId: KanbanStatus;
  count: number;
  actions: PreparedAction[];
  onActionClick: (action: PreparedAction) => void;
  onAddClick?: () => void;
  onClearAll?: () => void;
}

function KanbanColumn({ title, columnId, count, actions, onActionClick, onAddClick, onClearAll }: KanbanColumnProps) {
  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Column header */}
      <div className="flex items-center justify-between mb-2 flex-shrink-0">
        <h3 className="font-semibold text-sm text-gunmetal">
          {title} ({count})
        </h3>

        {columnId === 'queued' && onAddClick && (
          <button
            onClick={onAddClick}
            className="w-6 h-6 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 flex items-center justify-center transition-colors"
          >
            <Plus className="w-3.5 h-3.5 text-gray-600" />
          </button>
        )}

        {columnId === 'completed' && count > 0 && onClearAll && (
          <button
            onClick={onClearAll}
            className="text-xs text-gray-500 hover:text-gray-700 font-medium transition-colors"
          >
            Clear All
          </button>
        )}
      </div>

      {/* Droppable area */}
      <div className="flex-1 bg-gray-50/50 rounded-xl p-2 overflow-y-auto space-y-2 min-h-0">
        <SortableContext items={actions.map(a => a.id)} strategy={verticalListSortingStrategy}>
          {actions.map(action => (
            <SortableActionCard
              key={action.id}
              action={action}
              onClick={() => onActionClick(action)}
            />
          ))}
        </SortableContext>

        {actions.length === 0 && (
          <div className="flex items-center justify-center h-20 text-xs text-gray-400">
            No actions
          </div>
        )}
      </div>
    </div>
  );
}

// Problem Modal (Expanded View)
interface ProblemModalProps {
  problem: Problem | null;
  onClose: () => void;
  onApproveAction: (actionId: string) => void;
  onRejectAction: (actionId: string) => void;
  onViewDraft: (action: ActionOption) => void;
  loadingActionId?: string | null;
}

function ProblemModal({ problem, onClose, onApproveAction, onRejectAction, onViewDraft, loadingActionId }: ProblemModalProps) {
  if (!problem) return null;

  const severity = (problem.severity as Severity) || 'normal';
  const config = severityConfig[severity];

  return (
    <Dialog open={!!problem} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto bg-white">
        <DialogHeader className="pb-4 border-b border-gray-200">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className={cn('w-10 h-10 rounded-full flex items-center justify-center', config.bgClass)}>
                <AlertCircle className={cn('w-5 h-5', config.iconColor)} />
              </div>
              <div>
                <DialogTitle className="text-base font-semibold text-gunmetal">
                  {problem.title}
                </DialogTitle>
                <p className="text-xs text-gray-500 mt-1">
                  Detected: {formatDateTime(problem.detected_at)}
                </p>
              </div>
            </div>
            <span className={cn('px-2.5 py-1 rounded-full text-xs font-medium', config.bgClass, config.textClass)}>
              {config.label}
            </span>
          </div>
        </DialogHeader>

        {/* Context section */}
        {problem.context && problem.context.length > 0 && (
          <div className="py-4 border-b border-gray-200">
            <h3 className="font-semibold text-sm mb-2 text-gunmetal">Context</h3>
            <ul className="space-y-1.5 text-sm text-gray-600">
              {problem.context.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-gray-400 mt-0.5">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action options */}
        <div className="py-4">
          <h3 className="font-semibold text-sm mb-3 text-gunmetal">Your Options</h3>
          <div className="space-y-3">
            {problem.actions?.map((action) => (
              <ActionOptionCard
                key={action.id}
                action={action}
                onApprove={() => onApproveAction(action.id)}
                onReject={() => onRejectAction(action.id)}
                onViewDraft={() => onViewDraft(action)}
                isLoading={loadingActionId === action.id}
              />
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// View Draft Modal
interface ViewDraftModalProps {
  action: ActionOption | null;
  problem?: Problem | null;
  onClose: () => void;
  onApprove: () => void;
  onReject: () => void;
  isLoading?: boolean;
}

function ViewDraftModal({ action, problem, onClose, onApprove, onReject, isLoading }: ViewDraftModalProps) {
  const [copied, setCopied] = useState(false);

  if (!action) return null;

  const riskStyle = riskBadgeStyles[action.risk_level] || riskBadgeStyles.medium;

  const handleCopy = () => {
    const content = action.prepared_content;
    let textToCopy = '';

    if (content?.email_subject && content?.email_body) {
      textToCopy = `Subject: ${content.email_subject}\n\n${content.email_body}`;
    } else if (typeof content === 'string') {
      textToCopy = content;
    } else {
      textToCopy = JSON.stringify(content, null, 2);
    }

    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open={!!action} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto bg-white">
        <DialogHeader className="pb-4 border-b border-gray-200">
          <div className="flex items-start justify-between gap-4">
            <DialogTitle className="text-sm font-semibold text-gunmetal leading-snug pr-2">
              {action.title}
            </DialogTitle>
            <div className="flex items-center gap-2 flex-shrink-0">
              {action.is_recommended && (
                <span className="px-2 py-0.5 rounded-full bg-lime/20 text-lime-700 text-xs font-medium">
                  Recommended
                </span>
              )}
              <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', riskStyle)}>
                {action.risk_level.charAt(0).toUpperCase() + action.risk_level.slice(1)} Risk
              </span>
            </div>
          </div>
        </DialogHeader>

        {/* Problem context if available */}
        {problem && (
          <div className="py-3 border-b border-gray-200">
            <h3 className="text-xs font-semibold text-gunmetal mb-2">Problem Context</h3>
            <div className="p-2.5 rounded-lg bg-gray-50 text-sm text-gray-600">
              {problem.title}
            </div>
          </div>
        )}

        {/* Draft content preview */}
        <div className="py-3 border-b border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-gunmetal">Draft Content</h3>
            <Button variant="ghost" size="sm" onClick={handleCopy} className="h-7 text-xs">
              {copied ? (
                <>
                  <Check className="w-3 h-3 mr-1" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3 mr-1" />
                  Copy
                </>
              )}
            </Button>
          </div>
          <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
            {action.prepared_content?.email_subject && (
              <div className="mb-2">
                <span className="text-xs font-medium text-gray-500">Subject:</span>
                <p className="text-sm font-medium text-gunmetal">{action.prepared_content.email_subject}</p>
              </div>
            )}
            {action.prepared_content?.recipient && (
              <div className="mb-2">
                <span className="text-xs font-medium text-gray-500">To:</span>
                <p className="text-sm text-gunmetal">{action.prepared_content.recipient}</p>
              </div>
            )}
            <pre className="text-sm whitespace-pre-wrap font-sans text-gray-600">
              {action.prepared_content?.email_body ||
                action.prepared_content?.description ||
                JSON.stringify(action.prepared_content, null, 2)}
            </pre>
          </div>
        </div>

        {/* Action buttons */}
        <div className="pt-3 flex gap-2">
          <Button
            size="sm"
            onClick={onApprove}
            disabled={action.status === 'approved' || isLoading}
            className="flex-1 h-9 bg-lime hover:bg-lime/90 text-gunmetal text-sm font-medium"
          >
            {isLoading ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Check className="w-4 h-4 mr-1.5" />}
            {action.status === 'approved' ? 'Approved' : 'Approve'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onReject}
            disabled={action.status === 'rejected' || isLoading}
            className="h-9 border border-tomato text-tomato hover:bg-tomato/5 text-sm font-medium"
          >
            <X className="w-4 h-4 mr-1.5" />
            Reject
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Action Step Item Component
interface ActionStepItemProps {
  step: ActionStep;
  onToggle?: () => void;
  onEdit?: () => void;
}

function ActionStepItem({ step, onToggle, onEdit }: ActionStepItemProps) {
  const ownerBadge = step.owner === 'tamio' ? (
    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-600 border border-gray-200">
      Tamio
    </span>
  ) : (
    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-mimi-pink/30 text-gunmetal border border-mimi-pink/50">
      You
    </span>
  );

  return (
    <div className="flex items-center gap-2 py-1.5">
      <button
        onClick={onToggle}
        className={cn(
          "flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full border-2 transition-colors",
          step.status === 'completed'
            ? "bg-lime/20 border-lime-700"
            : "border-gray-300 hover:border-gray-400"
        )}
      >
        {step.status === 'completed' && <Check className="w-3 h-3 text-lime-700" />}
      </button>
      <span className={cn(
        "text-sm flex-1",
        step.status === 'completed' ? 'text-gray-400 line-through' : 'text-gunmetal'
      )}>
        {step.title}
      </span>
      {ownerBadge}
      {onEdit && step.status !== 'completed' && (
        <button
          onClick={onEdit}
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <Pencil className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}

// Collapsible Alert Section Component
interface LinkedAlertSectionProps {
  alert: LinkedAlert;
}

function LinkedAlertSection({ alert }: LinkedAlertSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const severity = alert.severity as Severity;
  const config = severityConfig[severity];

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 bg-white hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle className={cn('w-4 h-4', config.iconColor)} />
          <span className="font-medium text-sm text-gunmetal">{alert.title}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 border-t border-gray-100 bg-gray-50/50">
          <ul className="mt-2 space-y-1">
            {alert.context_summary.map((item, idx) => (
              <li key={idx} className="text-xs text-gray-600 flex items-start gap-2">
                <span className="text-gray-400 mt-0.5">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
          {alert.cash_impact && (
            <div className="mt-2 pt-2 border-t border-gray-200">
              <span className="text-xs text-gray-500">
                Cash Impact: <span className={alert.cash_impact < 0 ? 'text-tomato font-medium' : 'text-lime-700 font-medium'}>
                  {alert.cash_impact < 0 ? '-' : '+'}${formatAmount(Math.abs(alert.cash_impact))}
                </span>
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Email Preview Component for Ready to Execute section
interface EmailPreviewProps {
  content: Record<string, any>;
  onEdit: () => void;
  onCopy: () => void;
  onOpenInEmail: () => void;
  copied: boolean;
}

function EmailPreview({ content, onEdit, onCopy, onOpenInEmail, copied }: EmailPreviewProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="p-4">
        <p className="text-sm font-semibold text-gunmetal mb-2">Send Vendor Delay Message</p>

        <div className="space-y-1 text-sm text-gray-600 mb-3">
          <p><span className="text-gray-500">To:</span> {content.recipient || 'recipient@example.com'}</p>
          <p><span className="text-gray-500">Subject:</span> {content.email_subject || 'No subject'}</p>
        </div>

        <div className="text-sm text-gray-700 whitespace-pre-wrap">
          {content.email_body || 'No content'}
        </div>
      </div>

      <div className="flex gap-2 p-3 bg-gray-50 border-t border-gray-100">
        <button
          onClick={onEdit}
          className="flex-1 py-2 px-3 rounded-lg bg-mimi-pink/30 hover:bg-mimi-pink/50 border border-mimi-pink/50 text-sm font-medium text-gunmetal transition-colors"
        >
          Edit Email
        </button>
        <button
          onClick={onCopy}
          className="flex-1 py-2 px-3 rounded-lg bg-white hover:bg-gray-100 border border-gray-200 text-sm font-medium text-gunmetal transition-colors"
        >
          {copied ? 'Copied!' : 'Copy Email'}
        </button>
        <button
          onClick={onOpenInEmail}
          className="flex-1 py-2 px-3 rounded-lg bg-white hover:bg-gray-100 border border-gray-200 text-sm font-medium text-gunmetal transition-colors"
        >
          Open in Email
        </button>
      </div>
    </div>
  );
}

// Payment Details Preview Component
interface PaymentPreviewProps {
  content: Record<string, any>;
  impactAmount: number | null;
  deadline: string | null;
  onCopy: () => void;
  onDownloadCSV: () => void;
  copied: boolean;
}

function PaymentPreview({ content, impactAmount, deadline, onCopy, onDownloadCSV, copied }: PaymentPreviewProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="flex items-center justify-between p-3 border-b border-gray-100">
        <h4 className="text-sm font-medium text-gunmetal">Action Details</h4>
        <div className="flex gap-1">
          <button
            onClick={onCopy}
            className="flex items-center gap-1 px-2 py-1 rounded-md bg-white hover:bg-gray-100 border border-gray-200 text-xs font-medium text-gunmetal transition-colors"
          >
            <Copy className="w-3 h-3" />
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={onDownloadCSV}
            className="flex items-center gap-1 px-2 py-1 rounded-md bg-white hover:bg-gray-100 border border-gray-200 text-xs font-medium text-gunmetal transition-colors"
          >
            <Download className="w-3 h-3" />
            CSV
          </button>
        </div>
      </div>

      <div className="p-4">
        <div className="flex items-center gap-4 mb-3 text-sm text-gray-500">
          {impactAmount && (
            <span className="flex items-center gap-1">
              <DollarSign className="w-4 h-4" />
              Impact: ${formatAmount(impactAmount)}
            </span>
          )}
          {deadline && (
            <>
              <span className="w-1 h-1 rounded-full bg-gray-300" />
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                Due: {deadline}
              </span>
            </>
          )}
        </div>

        <p className="text-sm text-gray-700">
          {content.description || JSON.stringify(content, null, 2)}
        </p>
      </div>
    </div>
  );
}

// Action Detail Modal (for Kanban cards) - Redesigned to match mockup
interface ActionDetailModalProps {
  action: PreparedAction | null;
  onClose: () => void;
  onMarkComplete: () => void;
  isLoading?: boolean;
}

function ActionDetailModal({ action, onClose, onMarkComplete, isLoading }: ActionDetailModalProps) {
  const [copied, setCopied] = useState(false);
  const [localSteps, setLocalSteps] = useState<ActionStep[]>([]);

  // Sync local steps when action changes
  useEffect(() => {
    if (action?.action_steps) {
      setLocalSteps([...action.action_steps]);
    }
  }, [action?.id, action?.action_steps]);

  const handleToggleStep = (stepId: string) => {
    setLocalSteps(prev => prev.map(step => {
      if (step.id === stepId) {
        const newStatus = step.status === 'completed' ? 'pending' : 'completed';
        return { ...step, status: newStatus };
      }
      return step;
    }));
    // TODO: Call API to persist step status change
  };

  if (!action) return null;

  const urgency = (action.urgency as Severity) || 'normal';
  const urgencyBadges: Record<Severity, string> = {
    urgent: 'bg-tomato text-white',
    high: 'bg-yellow-500 text-white',
    normal: 'bg-gunmetal text-white',
  };

  const handleCopy = () => {
    const content = action.draft_content;
    let textToCopy = '';

    if (typeof content === 'string') {
      textToCopy = content;
    } else if (content?.email_body) {
      textToCopy = `To: ${content.recipient || ''}\nSubject: ${content.email_subject || ''}\n\n${content.email_body}`;
    } else {
      textToCopy = JSON.stringify(content, null, 2);
    }

    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleEditEmail = () => {
    toast.info('Email editing coming soon');
  };

  const handleOpenInEmail = () => {
    const content = action.draft_content;
    if (content?.email_body && content?.recipient) {
      const mailtoUrl = `mailto:${content.recipient}?subject=${encodeURIComponent(content.email_subject || '')}&body=${encodeURIComponent(content.email_body)}`;
      window.open(mailtoUrl, '_blank');
    } else {
      toast.info('Email client integration coming soon');
    }
  };

  const handleDownloadCSV = () => {
    console.log('Download CSV for action:', action.id);
    toast.info('CSV download coming soon');
  };

  const isEmailAction = action.action_type === 'email' && action.draft_content?.email_body;

  return (
    <Dialog open={!!action} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto bg-white p-0 [&>button]:hidden">
        {/* Header */}
        <div className="p-5 pb-4">
          <div className="flex items-start justify-between mb-1">
            <DialogTitle className="text-xl font-bold text-gunmetal pr-8">
              {action.title}
            </DialogTitle>
            <button
              onClick={onClose}
              className="absolute right-4 top-4 w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          {/* Approved date if available */}
          {action.approved_at && (
            <p className="text-xs text-gray-500 mb-3">
              Approved Task: {action.approved_at}
            </p>
          )}

          {/* Urgency and Due badges */}
          <div className="flex gap-2">
            <span className={cn(
              'px-4 py-1.5 rounded-full text-sm font-medium',
              urgencyBadges[urgency]
            )}>
              {urgency.charAt(0).toUpperCase() + urgency.slice(1)}
            </span>
            {action.deadline && (
              <span className={cn(
                'px-4 py-1.5 rounded-full text-sm font-medium',
                action.deadline.toLowerCase().includes('today') || action.deadline.toLowerCase().includes('overdue')
                  ? 'bg-tomato text-white'
                  : 'bg-gray-100 text-gunmetal'
              )}>
                {action.deadline}
              </span>
            )}
          </div>
        </div>

        {/* Content sections */}
        <div className="px-5 pb-5 space-y-4">
          {/* Linked Alert Section (collapsible) */}
          {action.linked_alert && (
            <LinkedAlertSection alert={action.linked_alert} />
          )}

          {/* Action Steps Section */}
          {localSteps.length > 0 && (
            <div className="rounded-xl border border-gray-200 overflow-hidden">
              <div className="flex items-center justify-between p-3 bg-white border-b border-gray-100">
                <h4 className="text-sm font-semibold text-gunmetal">Action Steps</h4>
                <button className="text-xs text-gray-500 hover:text-gunmetal font-medium transition-colors">
                  Edit
                </button>
              </div>
              <div className="p-3 bg-white">
                {localSteps
                  .sort((a, b) => a.order - b.order)
                  .map((step) => (
                    <ActionStepItem
                      key={step.id}
                      step={step}
                      onToggle={() => handleToggleStep(step.id)}
                    />
                  ))}
              </div>
            </div>
          )}

          {/* Ready to Execute Section */}
          <div>
            <h4 className="text-base font-semibold text-gunmetal mb-3 text-center">
              Ready to Execute
            </h4>

            {isEmailAction ? (
              <EmailPreview
                content={action.draft_content}
                onEdit={handleEditEmail}
                onCopy={handleCopy}
                onOpenInEmail={handleOpenInEmail}
                copied={copied}
              />
            ) : (
              <PaymentPreview
                content={action.draft_content}
                impactAmount={action.impact_amount}
                deadline={action.deadline}
                onCopy={handleCopy}
                onDownloadCSV={handleDownloadCSV}
                copied={copied}
              />
            )}
          </div>

          {/* Mark Complete button (only for non-completed actions) */}
          {action.status !== 'completed' && (
            <Button
              onClick={onMarkComplete}
              disabled={isLoading}
              className="w-full h-11 bg-lime hover:bg-lime/90 text-gunmetal text-sm font-semibold rounded-full"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Check className="w-4 h-4 mr-2" />
              )}
              Mark as Completed
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Create Action Modal
interface CreateActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateActionRequest) => Promise<void>;
  isLoading?: boolean;
}

function CreateActionModal({ isOpen, onClose, onSubmit, isLoading }: CreateActionModalProps) {
  const [formData, setFormData] = useState<CreateActionRequest>({
    title: '',
    action_type: 'manual',
    priority: 'normal',
    due_date: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title || !formData.due_date) {
      toast.error('Please fill in all required fields');
      return;
    }
    await onSubmit(formData);
    setFormData({ title: '', action_type: 'manual', priority: 'normal', due_date: '' });
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md bg-white">
        <DialogHeader>
          <DialogTitle className="text-sm font-semibold text-gunmetal">Create Manual Action</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3 pt-3">
          {/* Action Title */}
          <div>
            <label className="block font-medium mb-1 text-xs text-gunmetal">Action Title *</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 bg-white focus:border-tomato focus:ring-1 focus:ring-tomato outline-none transition-colors text-sm"
              placeholder="e.g., Send quarterly report to CFO"
            />
          </div>

          {/* Action Type */}
          <div>
            <label className="block font-medium mb-1 text-xs text-gunmetal">Action Type *</label>
            <Select value={formData.action_type} onValueChange={(value: ActionType) => setFormData(prev => ({ ...prev, action_type: value }))}>
              <SelectTrigger className="w-full h-9 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="payment_batch">Payment Batch</SelectItem>
                <SelectItem value="transfer">Transfer</SelectItem>
                <SelectItem value="manual">Manual Task</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Priority */}
          <div>
            <label className="block font-medium mb-1 text-xs text-gunmetal">Priority *</label>
            <Select value={formData.priority} onValueChange={(value: Severity) => setFormData(prev => ({ ...prev, priority: value }))}>
              <SelectTrigger className="w-full h-9 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="urgent">Urgent</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Due Date */}
          <div>
            <label className="block font-medium mb-1 text-xs text-gunmetal">Due Date *</label>
            <input
              type="date"
              value={formData.due_date}
              onChange={(e) => setFormData(prev => ({ ...prev, due_date: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 bg-white focus:border-tomato focus:ring-1 focus:ring-tomato outline-none transition-colors text-sm"
            />
          </div>

          {/* Impact Amount (Optional) */}
          <div>
            <label className="block font-medium mb-1 text-xs text-gunmetal">Impact Amount (Optional)</label>
            <input
              type="number"
              value={formData.impact_amount || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, impact_amount: e.target.value ? Number(e.target.value) : undefined }))}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 bg-white focus:border-tomato focus:ring-1 focus:ring-tomato outline-none transition-colors text-sm"
              placeholder="e.g., 52500"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block font-medium mb-1 text-xs text-gunmetal">Notes (Optional)</label>
            <textarea
              rows={2}
              value={formData.notes || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value || undefined }))}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 bg-white focus:border-tomato focus:ring-1 focus:ring-tomato outline-none transition-colors resize-none text-sm"
              placeholder="Additional context..."
            />
          </div>

          {/* Buttons */}
          <div className="flex gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="flex-1 h-9 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-sm font-medium"
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="flex-1 h-9 rounded-lg bg-tomato hover:bg-tomato/90 text-white text-sm font-medium"
              disabled={isLoading}
            >
              {isLoading ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : null}
              Create Action
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// Agents Dialog Component
interface AgentsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function AgentsDialog({ open, onOpenChange }: AgentsDialogProps) {
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  const activeAgents = agents.filter(a => a.status === 'active').length;
  const detectionAgents = agents.filter(a => a.category === 'detection' || a.category === 'core');
  const preparationAgents = agents.filter(a => a.category === 'preparation');

  // If an agent is selected, show detail view
  if (selectedAgent) {
    const Icon = selectedAgent.icon;
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto bg-white">
          <DialogHeader>
            <div className="flex items-start gap-4">
              <button
                onClick={() => setSelectedAgent(null)}
                className="p-2 -ml-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <ChevronRight className="w-5 h-5 rotate-180 text-gunmetal/60" />
              </button>
              <div className={`p-3 rounded-xl ${selectedAgent.accentColor.split(' ')[0]} border ${selectedAgent.accentColor.split(' ')[2]}`}>
                <Icon className={`w-6 h-6 ${selectedAgent.accentColor.split(' ')[1]}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <DialogTitle className="text-xl">{selectedAgent.name}</DialogTitle>
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-lime/20 text-lime-700">
                    Active
                  </span>
                </div>
                <p className="text-sm text-gunmetal/60 mt-1">
                  {selectedAgent.purpose}
                </p>
              </div>
            </div>
          </DialogHeader>

          {/* Meta info */}
          <div className="flex flex-wrap gap-3 py-3 border-b border-gunmetal/10">
            <span className="text-xs text-gunmetal/60 flex items-center gap-1 bg-gray-50 px-2 py-1 rounded-md">
              <Zap className="w-3 h-3" />
              {selectedAgent.intelligenceType}
            </span>
            <span className="text-xs text-gunmetal/60 flex items-center gap-1 bg-gray-50 px-2 py-1 rounded-md">
              <Activity className="w-3 h-3" />
              Runs: {selectedAgent.runFrequency}
            </span>
          </div>

          {/* What It Does */}
          <div className="py-4">
            <h4 className="text-sm font-semibold text-gunmetal mb-3">What It Does</h4>
            <ul className="space-y-2">
              {selectedAgent.whatItDoes.map((item, index) => (
                <li key={index} className="flex items-start gap-2 text-sm text-gunmetal/70">
                  <span className="text-gunmetal/40 mt-0.5">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Metrics */}
          <div className="py-4 border-t border-gunmetal/10">
            <h4 className="text-sm font-semibold text-gunmetal mb-3">Metrics</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {selectedAgent.metrics.map((metric) => (
                <div
                  key={metric.label}
                  className="p-3 bg-gray-50 rounded-lg border border-gray-100"
                >
                  <div className="text-lg font-bold text-gunmetal">{metric.value}</div>
                  <div className="text-xs text-gunmetal/50">{metric.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2 pt-4 border-t border-gunmetal/10">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 border-gray-200 hover:bg-gray-50"
              onClick={() => toast.info('Agent settings coming soon')}
            >
              <Settings className="w-4 h-4 mr-1.5" />
              View Settings
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 border-gray-200 hover:bg-gray-50"
              onClick={() => toast.info('Agent activity log coming soon')}
            >
              <Activity className="w-4 h-4 mr-1.5" />
              View Activity
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // Main agents list view
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto bg-white">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle className="text-xl">Your Treasury Agents</DialogTitle>
              <p className="text-sm text-gunmetal/60 mt-1">
                AI-powered agents that continuously monitor your cash flow and prepare actions for your approval.
              </p>
            </div>
          </div>
        </DialogHeader>

        {/* Summary Stats */}
        <div className="flex gap-4 py-4 border-b border-gray-100">
          <div className="px-4 py-2 bg-gray-50 rounded-lg">
            <div className="text-xl font-bold text-gunmetal">{activeAgents}</div>
            <div className="text-xs text-gunmetal/60">Active Agents</div>
          </div>
          <div className="px-4 py-2 bg-gray-50 rounded-lg">
            <div className="text-xl font-bold text-lime-700">31</div>
            <div className="text-xs text-gunmetal/60">Checks This Week</div>
          </div>
          <div className="px-4 py-2 bg-gray-50 rounded-lg">
            <div className="text-xl font-bold text-amber-600">8</div>
            <div className="text-xs text-gunmetal/60">Actions Completed</div>
          </div>
        </div>

        {/* Detection Agents */}
        <div className="py-4">
          <h4 className="text-sm font-semibold text-gunmetal mb-3 flex items-center gap-2">
            <Eye className="w-4 h-4 text-purple-600" />
            Detection Agents
            <span className="text-xs font-normal text-gunmetal/50">Monitor and alert</span>
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {detectionAgents.map((agent) => {
              const Icon = agent.icon;
              return (
                <div
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent)}
                  className="p-4 rounded-xl bg-gray-50 border border-gray-100 hover:border-gray-200 hover:bg-gray-100/50 cursor-pointer transition-all group"
                >
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg ${agent.accentColor.split(' ')[0]} border ${agent.accentColor.split(' ')[2]}`}>
                      <Icon className={`w-5 h-5 ${agent.accentColor.split(' ')[1]}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <h5 className="font-medium text-sm text-gunmetal">{agent.name}</h5>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-lime/20 text-lime-700">
                          Active
                        </span>
                      </div>
                      <p className="text-xs text-gunmetal/60 mt-1 line-clamp-2">{agent.purpose}</p>
                      <div className="flex items-center gap-1 mt-2 text-xs text-gunmetal/50 group-hover:text-gunmetal transition-colors">
                        <span>View details</span>
                        <ArrowRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Preparation Agents */}
        <div className="py-4 border-t border-gray-100">
          <h4 className="text-sm font-semibold text-gunmetal mb-3 flex items-center gap-2">
            <FileText className="w-4 h-4 text-amber-600" />
            Preparation Agents
            <span className="text-xs font-normal text-gunmetal/50">Draft and prepare actions</span>
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {preparationAgents.map((agent) => {
              const Icon = agent.icon;
              return (
                <div
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent)}
                  className="p-4 rounded-xl bg-gray-50 border border-gray-100 hover:border-gray-200 hover:bg-gray-100/50 cursor-pointer transition-all group"
                >
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg ${agent.accentColor.split(' ')[0]} border ${agent.accentColor.split(' ')[2]}`}>
                      <Icon className={`w-5 h-5 ${agent.accentColor.split(' ')[1]}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <h5 className="font-medium text-sm text-gunmetal">{agent.name}</h5>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-lime/20 text-lime-700">
                          Active
                        </span>
                      </div>
                      <p className="text-xs text-gunmetal/60 mt-1 line-clamp-2">{agent.purpose}</p>
                      <div className="flex items-center gap-1 mt-2 text-xs text-gunmetal/50 group-hover:text-gunmetal transition-colors">
                        <span>View details</span>
                        <ArrowRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function ActionMonitor() {
  // URL parameters for deep linking
  const [searchParams] = useSearchParams();
  const alertIdParam = searchParams.get('alert');

  // State
  const [problems, setProblems] = useState<Problem[]>([]);
  const [actions, setActions] = useState<{ queued: PreparedAction[]; executing: PreparedAction[]; completed: PreparedAction[] }>({
    queued: [],
    executing: [],
    completed: [],
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastSyncTime, setLastSyncTime] = useState<string>('');

  // Modal state
  const [selectedProblem, setSelectedProblem] = useState<Problem | null>(null);
  const [selectedDraftAction, setSelectedDraftAction] = useState<ActionOption | null>(null);
  const [selectedDraftProblem, setSelectedDraftProblem] = useState<Problem | null>(null);
  const [selectedKanbanAction, setSelectedKanbanAction] = useState<PreparedAction | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [loadingActionId, setLoadingActionId] = useState<string | null>(null);
  const [agentsDialogOpen, setAgentsDialogOpen] = useState(false);

  // Carousel state
  const carouselRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Kanban filters
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('due_date');

  // Alert filters (for problem carousel)
  const [alertPriorityFilter, setAlertPriorityFilter] = useState<string>('all');
  const [alertTimeFilter, setAlertTimeFilter] = useState<string>('all');

  // Drag and drop state
  const [activeId, setActiveId] = useState<string | null>(null);

  // Sensors for drag and drop
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor)
  );

  // Check carousel scroll state
  const checkCarouselScroll = useCallback(() => {
    if (carouselRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = carouselRef.current;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 10);
    }
  }, []);

  useEffect(() => {
    checkCarouselScroll();
    const carousel = carouselRef.current;
    if (carousel) {
      carousel.addEventListener('scroll', checkCarouselScroll);
      return () => carousel.removeEventListener('scroll', checkCarouselScroll);
    }
  }, [checkCarouselScroll, problems]);

  // Carousel scroll handlers
  const scrollCarousel = (direction: 'left' | 'right') => {
    if (carouselRef.current) {
      const scrollAmount = carouselRef.current.clientWidth / 3 + 16;
      carouselRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      let problemsData: Problem[];
      let actionsData: { queued: PreparedAction[]; executing: PreparedAction[]; completed: PreparedAction[] };

      try {
        [problemsData, actionsData] = await Promise.all([
          getProblemsToReview(),
          getActions(),
        ]);
      } catch {
        problemsData = MOCK_PROBLEMS;
        actionsData = MOCK_ACTIONS;
      }

      setProblems(problemsData);
      setActions(actionsData);
      setLastSyncTime(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Failed to fetch action monitor data:', err);
      setError('Failed to load data. Using demo data.');
      setProblems(MOCK_PROBLEMS);
      setActions(MOCK_ACTIONS);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-expand alert if URL parameter is present
  useEffect(() => {
    if (alertIdParam && problems.length > 0 && !isLoading) {
      const alertToExpand = problems.find((p) => p.id === alertIdParam);
      if (alertToExpand) {
        setSelectedProblem(alertToExpand);
      }
    }
  }, [alertIdParam, problems, isLoading]);

  // Filter and sort actions
  const filteredActions = useMemo(() => {
    const filterByPriority = (actionList: PreparedAction[]) => {
      if (priorityFilter === 'all') return actionList;
      return actionList.filter(a => a.urgency === priorityFilter);
    };

    const sortActions = (actionList: PreparedAction[]) => {
      return [...actionList].sort((a, b) => {
        if (sortBy === 'due_date') {
          if (!a.deadline) return 1;
          if (!b.deadline) return -1;
          return a.deadline.localeCompare(b.deadline);
        }
        if (sortBy === 'priority') {
          const priorityOrder: Record<Severity, number> = { urgent: 0, high: 1, normal: 2 };
          return priorityOrder[a.urgency as Severity] - priorityOrder[b.urgency as Severity];
        }
        if (sortBy === 'impact') {
          return (b.impact_amount || 0) - (a.impact_amount || 0);
        }
        return 0;
      });
    };

    return {
      queued: sortActions(filterByPriority(actions.queued)),
      executing: sortActions(filterByPriority(actions.executing)),
      completed: sortActions(filterByPriority(actions.completed)),
    };
  }, [actions, priorityFilter, sortBy]);

  // Filter problems (alerts) based on priority and time filters
  const filteredProblems = useMemo(() => {
    return problems.filter((problem) => {
      // Priority filter
      if (alertPriorityFilter !== 'all') {
        if (alertPriorityFilter === 'resolved') {
          // Check if all actions are approved or rejected
          const allResolved = problem.actions?.every(
            (a) => a.status === 'approved' || a.status === 'rejected'
          );
          if (!allResolved) return false;
        } else if (problem.severity !== alertPriorityFilter) {
          return false;
        }
      }

      // Time filter
      if (alertTimeFilter !== 'all') {
        const now = new Date();
        const detectedAt = new Date(problem.detected_at);
        const title = problem.title.toLowerCase();

        if (alertTimeFilter === 'today') {
          // Check if due today (look for "today" or "due today" in title/deadline)
          const isToday = title.includes('today') || title.includes('due friday');
          if (!isToday) return false;
        } else if (alertTimeFilter === 'week') {
          // Due within this week (7 days)
          const daysDiff = Math.ceil((now.getTime() - detectedAt.getTime()) / (1000 * 60 * 60 * 24));
          if (daysDiff > 7) return false;
        } else if (alertTimeFilter === 'month') {
          // Due within this month (30 days)
          const daysDiff = Math.ceil((now.getTime() - detectedAt.getTime()) / (1000 * 60 * 60 * 24));
          if (daysDiff > 30) return false;
        }
      }

      return true;
    });
  }, [problems, alertPriorityFilter, alertTimeFilter]);

  // Action handlers
  const handleApproveAction = async (actionId: string) => {
    setLoadingActionId(actionId);
    try {
      await approveActionOption(actionId);
      setProblems((prev) =>
        prev.map((p) => ({
          ...p,
          actions: p.actions?.map((a) => (a.id === actionId ? { ...a, status: 'approved' as const } : a)),
        }))
      );
      toast.success('Action approved');
      if (selectedDraftAction?.id === actionId) {
        setSelectedDraftAction(null);
        setSelectedDraftProblem(null);
      }
    } catch (err) {
      console.error('Failed to approve action:', err);
      toast.error('Failed to approve action');
    } finally {
      setLoadingActionId(null);
    }
  };

  const handleRejectAction = async (actionId: string) => {
    setLoadingActionId(actionId);
    try {
      await rejectActionOption(actionId);
      setProblems((prev) =>
        prev.map((p) => ({
          ...p,
          actions: p.actions?.map((a) => (a.id === actionId ? { ...a, status: 'rejected' as const } : a)),
        }))
      );
      toast.success('Action rejected');
      if (selectedDraftAction?.id === actionId) {
        setSelectedDraftAction(null);
        setSelectedDraftProblem(null);
      }
    } catch (err) {
      console.error('Failed to reject action:', err);
      toast.error('Failed to reject action');
    } finally {
      setLoadingActionId(null);
    }
  };

  const handleDismissProblem = async (problemId: string) => {
    try {
      await dismissProblem(problemId);
      setProblems((prev) => prev.filter((p) => p.id !== problemId));
      toast.success('Problem dismissed');
    } catch (err) {
      console.error('Failed to dismiss problem:', err);
      toast.error('Failed to dismiss problem');
    }
  };

  const handleMarkComplete = async (actionId: string) => {
    setLoadingActionId(actionId);
    try {
      await markActionComplete(actionId);
      setActions((prev) => {
        const action = [...prev.queued, ...prev.executing].find(a => a.id === actionId);
        if (!action) return prev;

        return {
          queued: prev.queued.filter(a => a.id !== actionId),
          executing: prev.executing.filter(a => a.id !== actionId),
          completed: [{ ...action, status: 'completed' as const, completed_at: new Date().toISOString() }, ...prev.completed],
        };
      });
      setSelectedKanbanAction(null);
      toast.success('Action marked as completed');
    } catch (err) {
      console.error('Failed to mark action complete:', err);
      toast.error('Failed to mark action complete');
    } finally {
      setLoadingActionId(null);
    }
  };

  const handleCreateAction = async (data: CreateActionRequest) => {
    setLoadingActionId('create');
    try {
      const response = await createAction(data);
      if (response.success && response.action) {
        setActions((prev) => ({
          ...prev,
          queued: [response.action, ...prev.queued],
        }));
        setIsCreateModalOpen(false);
        toast.success('Action created');
      }
    } catch (err) {
      console.error('Failed to create action:', err);
      const mockAction: PreparedAction = {
        id: `manual-${Date.now()}`,
        title: data.title,
        action_type: data.action_type,
        urgency: data.priority,
        impact_amount: data.impact_amount || null,
        deadline: data.due_date,
        problem_context: null,
        is_recurring: false,
        draft_content: { notes: data.notes },
        status: 'queued',
        is_system_generated: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setActions((prev) => ({
        ...prev,
        queued: [mockAction, ...prev.queued],
      }));
      setIsCreateModalOpen(false);
      toast.success('Action created');
    } finally {
      setLoadingActionId(null);
    }
  };

  const handleArchiveCompleted = async () => {
    try {
      await archiveCompletedActions();
      setActions((prev) => ({ ...prev, completed: [] }));
      toast.success('Completed actions archived');
    } catch (err) {
      console.error('Failed to archive completed actions:', err);
      setActions((prev) => ({ ...prev, completed: [] }));
      toast.success('Completed actions archived');
    }
  };

  // Drag and drop handlers
  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveId(null);

    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    let sourceColumn: KanbanStatus | null = null;
    let targetColumn: KanbanStatus | null = null;
    let draggedAction: PreparedAction | null = null;

    if (actions.queued.find(a => a.id === activeId)) {
      sourceColumn = 'queued';
      draggedAction = actions.queued.find(a => a.id === activeId) || null;
    } else if (actions.executing.find(a => a.id === activeId)) {
      sourceColumn = 'executing';
      draggedAction = actions.executing.find(a => a.id === activeId) || null;
    } else if (actions.completed.find(a => a.id === activeId)) {
      sourceColumn = 'completed';
      draggedAction = actions.completed.find(a => a.id === activeId) || null;
    }

    if (!draggedAction || !sourceColumn) return;

    if (overId === 'queued' || actions.queued.find(a => a.id === overId)) {
      targetColumn = 'queued';
    } else if (overId === 'executing' || actions.executing.find(a => a.id === overId)) {
      targetColumn = 'executing';
    } else if (overId === 'completed' || actions.completed.find(a => a.id === overId)) {
      targetColumn = 'completed';
    }

    if (!targetColumn || sourceColumn === targetColumn) return;

    setActions((prev) => {
      const updatedAction = { ...draggedAction!, status: targetColumn as KanbanStatus };

      return {
        queued: targetColumn === 'queued'
          ? [updatedAction, ...prev.queued.filter(a => a.id !== activeId)]
          : prev.queued.filter(a => a.id !== activeId),
        executing: targetColumn === 'executing'
          ? [updatedAction, ...prev.executing.filter(a => a.id !== activeId)]
          : prev.executing.filter(a => a.id !== activeId),
        completed: targetColumn === 'completed'
          ? [{ ...updatedAction, completed_at: new Date().toISOString() }, ...prev.completed.filter(a => a.id !== activeId)]
          : prev.completed.filter(a => a.id !== activeId),
      };
    });

    try {
      await updateActionStatus(activeId, targetColumn);
      toast.success(`Action moved to ${targetColumn}`);
    } catch (err) {
      console.error('Failed to update action status:', err);
      toast.info(`Action moved to ${targetColumn} (offline mode)`);
    }
  };

  const activeAction = activeId
    ? [...actions.queued, ...actions.executing, ...actions.completed].find(a => a.id === activeId)
    : null;

  // Loading state
  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex items-center gap-2 text-gray-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading action monitor...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden max-w-full">
      {/* Error banner */}
      {error && (
        <div className="mb-3 p-2.5 rounded-lg bg-yellow-50 border border-yellow-200 text-yellow-800 text-xs flex-shrink-0">
          {error}
        </div>
      )}

      {/* ================================================================== */}
      {/* SECTION 1: ALERTS WITH FILTER BAR */}
      {/* ================================================================== */}
      <NeuroCard className="flex-shrink-0 mb-4 p-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gunmetal">
            Alerts ({problems.length})
          </h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">
              Last sync: {lastSyncTime}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              disabled={isLoading}
              className="px-2.5 py-1 h-7 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-medium"
            >
              <RefreshCw className={cn('w-3 h-3 mr-1.5', isLoading && 'animate-spin')} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="flex items-center gap-4 mb-4 pb-3 border-b border-gray-100">
          {/* Priority Filters */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500 mr-2">Priority:</span>
            {[
              { value: 'all', label: 'All' },
              { value: 'urgent', label: 'Urgent' },
              { value: 'high', label: 'High' },
              { value: 'normal', label: 'Normal' },
              { value: 'resolved', label: 'Resolved' },
            ].map((filter) => (
              <button
                key={filter.value}
                onClick={() => setAlertPriorityFilter(filter.value)}
                className={cn(
                  'px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
                  alertPriorityFilter === filter.value
                    ? filter.value === 'urgent'
                      ? 'bg-tomato text-white'
                      : filter.value === 'high'
                      ? 'bg-yellow-500 text-white'
                      : filter.value === 'normal'
                      ? 'bg-lime text-gunmetal'
                      : filter.value === 'resolved'
                      ? 'bg-gray-600 text-white'
                      : 'bg-gunmetal text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <div className="w-px h-6 bg-gray-200" />

          {/* Time Filters */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500 mr-2">Due:</span>
            {[
              { value: 'all', label: 'All' },
              { value: 'today', label: 'Due Today' },
              { value: 'week', label: 'This Week' },
              { value: 'month', label: 'This Month' },
            ].map((filter) => (
              <button
                key={filter.value}
                onClick={() => setAlertTimeFilter(filter.value)}
                className={cn(
                  'px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
                  alertTimeFilter === filter.value
                    ? 'bg-gunmetal text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>

          {/* Active filter count */}
          {(alertPriorityFilter !== 'all' || alertTimeFilter !== 'all') && (
            <div className="ml-auto flex items-center gap-2">
              <span className="text-xs text-gray-500">
                Showing {filteredProblems.length} of {problems.length}
              </span>
              <button
                onClick={() => {
                  setAlertPriorityFilter('all');
                  setAlertTimeFilter('all');
                }}
                className="text-xs text-tomato hover:underline"
              >
                Clear filters
              </button>
            </div>
          )}
        </div>

        {filteredProblems.length === 0 ? (
          <div className="p-5 text-center">
            <Check className="h-5 w-5 mx-auto text-lime mb-1.5" />
            <p className="text-sm text-gray-500">
              {problems.length === 0
                ? "No alerts. You're all caught up!"
                : 'No alerts match your filters.'}
            </p>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            {/* Left arrow - outside carousel */}
            <button
              onClick={() => scrollCarousel('left')}
              disabled={!canScrollLeft}
              className={cn(
                "flex-shrink-0 w-9 h-9 rounded-full bg-white shadow-sm border border-gray-200 flex items-center justify-center transition-all",
                canScrollLeft ? "hover:bg-gray-50 hover:shadow-md" : "opacity-40 cursor-not-allowed"
              )}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            {/* Card container - with padding for shadows */}
            <div
              ref={carouselRef}
              className="flex-1 flex gap-4 overflow-x-auto scrollbar-hide py-2"
              style={{ scrollSnapType: 'x mandatory' }}
            >
              {filteredProblems.map(problem => (
                <ProblemCard
                  key={problem.id}
                  problem={problem}
                  onExpand={() => setSelectedProblem(problem)}
                  onDismiss={() => handleDismissProblem(problem.id)}
                />
              ))}
            </div>

            {/* Right arrow - outside carousel */}
            <button
              onClick={() => scrollCarousel('right')}
              disabled={!canScrollRight}
              className={cn(
                "flex-shrink-0 w-9 h-9 rounded-full bg-white shadow-sm border border-gray-200 flex items-center justify-center transition-all",
                canScrollRight ? "hover:bg-gray-50 hover:shadow-md" : "opacity-40 cursor-not-allowed"
              )}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </NeuroCard>

      {/* ================================================================== */}
      {/* SECTION 2: ACTION KANBAN BOARD */}
      {/* ================================================================== */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="flex items-center justify-between mb-3 flex-shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-semibold text-gunmetal">
              Action Queue
            </h2>
            <button
              onClick={() => setAgentsDialogOpen(true)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 border border-gray-200 transition-colors"
            >
              <Bot className="w-4 h-4 text-gunmetal/60" />
              <span className="text-sm font-medium text-gunmetal/80">{agents.length} Agents Active</span>
              <ChevronRight className="w-4 h-4 text-gunmetal/40" />
            </button>
          </div>

          {/* Filters and controls */}
          <div className="flex items-center gap-2">
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-[120px] h-7 text-xs">
                <SelectValue placeholder="All Priorities" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="urgent">Urgent</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
              </SelectContent>
            </Select>

            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-[160px] h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="due_date">Sort by: Due Date</SelectItem>
                <SelectItem value="priority">Sort by: Priority</SelectItem>
                <SelectItem value="impact">Sort by: Impact</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Kanban columns */}
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex-1 grid grid-cols-3 gap-3 min-h-0 overflow-hidden">
            <KanbanColumn
              title="Queued"
              columnId="queued"
              count={filteredActions.queued.length}
              actions={filteredActions.queued}
              onActionClick={setSelectedKanbanAction}
              onAddClick={() => setIsCreateModalOpen(true)}
            />
            <KanbanColumn
              title="Executing"
              columnId="executing"
              count={filteredActions.executing.length}
              actions={filteredActions.executing}
              onActionClick={setSelectedKanbanAction}
            />
            <KanbanColumn
              title="Completed"
              columnId="completed"
              count={filteredActions.completed.length}
              actions={filteredActions.completed}
              onActionClick={setSelectedKanbanAction}
              onClearAll={handleArchiveCompleted}
            />
          </div>

          {/* Drag overlay */}
          <DragOverlay>
            {activeAction && (
              <KanbanActionCard action={activeAction} onClick={() => {}} isDragging />
            )}
          </DragOverlay>
        </DndContext>
      </div>

      {/* ================================================================== */}
      {/* MODALS */}
      {/* ================================================================== */}

      {/* Problem Modal */}
      <ProblemModal
        problem={selectedProblem}
        onClose={() => setSelectedProblem(null)}
        onApproveAction={handleApproveAction}
        onRejectAction={handleRejectAction}
        onViewDraft={(action) => {
          setSelectedDraftAction(action);
          setSelectedDraftProblem(selectedProblem);
        }}
        loadingActionId={loadingActionId}
      />

      {/* View Draft Modal */}
      <ViewDraftModal
        action={selectedDraftAction}
        problem={selectedDraftProblem}
        onClose={() => {
          setSelectedDraftAction(null);
          setSelectedDraftProblem(null);
        }}
        onApprove={() => selectedDraftAction && handleApproveAction(selectedDraftAction.id)}
        onReject={() => selectedDraftAction && handleRejectAction(selectedDraftAction.id)}
        isLoading={loadingActionId === selectedDraftAction?.id}
      />

      {/* Action Detail Modal (Kanban) */}
      <ActionDetailModal
        action={selectedKanbanAction}
        onClose={() => setSelectedKanbanAction(null)}
        onMarkComplete={() => selectedKanbanAction && handleMarkComplete(selectedKanbanAction.id)}
        isLoading={loadingActionId === selectedKanbanAction?.id}
      />

      {/* Create Action Modal */}
      <CreateActionModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreateAction}
        isLoading={loadingActionId === 'create'}
      />

      {/* Agents Dialog */}
      <AgentsDialog
        open={agentsDialogOpen}
        onOpenChange={setAgentsDialogOpen}
      />
    </div>
  );
}
