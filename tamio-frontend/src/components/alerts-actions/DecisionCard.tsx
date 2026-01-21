/**
 * DecisionCard Component
 *
 * Displays an alert card with suggested actions.
 * This is the primary card shown in the "Requires Your Decision" section.
 *
 * Structure:
 * - Title (bold)
 * - TAMI's insight (context about the situation)
 * - Linked client/expense pill + Urgency tag + Due date tag
 * - Suggested Actions (actual actionable items)
 * - Action buttons: Approve | Modify | Dismiss
 */

import { useState, useRef, useEffect } from 'react';
import {
  Clock,
  Loader2,
  MessageCircle,
  TrendingUp,
  User,
  Receipt,
  Mail,
  Phone,
  FileText,
  AlertTriangle,
  Calendar,
  Building2,
  Users,
  DollarSign,
  ArrowDownRight,
  Wallet,
  X,
  Plus,
  Check
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DecisionItem } from '@/lib/api/alertsActions';
import { getSeverityStyles } from '@/lib/api/alertsActions';
import { formatAmount } from '@/lib/utils/decisionQueue';

interface DecisionCardProps {
  item: DecisionItem;
  onApprove: (controlId: string) => Promise<void>;
  onModify: (item: DecisionItem) => void;
  onDismiss: (riskId: string) => Promise<void>;
  onChatWithTami?: (item: DecisionItem) => void;
  onRunScenario?: (item: DecisionItem) => void;
}

// Type for context_data which varies by detection type
type ContextData = Record<string, unknown>;

/**
 * Extract linked entity info from context_data
 * Uses actual backend data structures for accurate extraction
 */
function getLinkedEntity(item: DecisionItem): {
  type: 'client' | 'expense' | 'payroll' | 'tax' | 'vendor' | null;
  name: string | null;
  details?: string;
} {
  const context = (item.alert as { context_data?: ContextData }).context_data || {};

  // Check for client name directly in context
  if (context.client_name) {
    return {
      type: 'client',
      name: context.client_name as string,
      details: context.relationship_type as string
    };
  }

  // Check for payroll-related alerts
  if (context.payroll_amount || context.obligation_category === 'payroll') {
    return {
      type: 'payroll',
      name: 'Payroll',
      details: context.payroll_date as string
    };
  }

  // Check for tax/statutory deadlines
  if (context.obligation_type?.toString().toLowerCase().includes('tax') ||
      context.obligation_category === 'tax_obligation') {
    return {
      type: 'tax',
      name: context.obligation_name as string || 'Tax Payment',
      details: context.due_date as string
    };
  }

  // Check for vendor/expense bucket
  if (context.vendor_name || context.bucket_name) {
    return {
      type: 'vendor',
      name: (context.vendor_name || context.bucket_name) as string,
      details: context.category as string
    };
  }

  // Fallback: Try to extract from primary_driver
  const driver = item.alert.primary_driver || '';
  const clientMatch = driver.match(/^([A-Z][a-zA-Z\s]+(?:Inc|Co|LLC|Corp|Ltd)?)/);
  if (clientMatch) {
    return { type: 'client', name: clientMatch[1].trim() };
  }

  return { type: null, name: null };
}

/**
 * Generate personalized insight text based on alert context
 */
function getInsightText(item: DecisionItem): string {
  const context = (item.alert as { context_data?: ContextData }).context_data || {};
  const recommendation = item.recommendation;

  // If we have a recommendation with why_it_exists, use that
  // But skip if it's just "Created in response to: [title]" which is not helpful
  if (recommendation?.why_it_exists &&
      !recommendation.why_it_exists.toLowerCase().startsWith('created in response to')) {
    return recommendation.why_it_exists;
  }

  // Generate contextual insight based on detection type and data
  const title = item.alert.title.toLowerCase();

  // Late payment insights
  if (title.includes('overdue') || title.includes('late')) {
    const daysOverdue = context.days_overdue as number;
    const avgDelay = context.avg_delay_days as number;
    const clientName = context.client_name as string;

    if (avgDelay && daysOverdue && daysOverdue > avgDelay) {
      return `This is ${daysOverdue - avgDelay} days beyond ${clientName || 'their'} typical payment pattern. Consider escalating follow-up.`;
    } else if (daysOverdue && daysOverdue > 14) {
      return `Payment is significantly overdue. A firm but professional follow-up is recommended to maintain cash flow.`;
    } else if (context.relationship_type === 'strategic') {
      return `This is a strategic client. Consider a personal call before sending formal reminders.`;
    }
  }

  // Payroll insights
  if (title.includes('payroll')) {
    const bufferAfter = context.buffer_after_payroll as number || context.cash_after_payroll as number;
    const shortfall = context.shortfall as number;

    if (shortfall && shortfall > 0) {
      return `You'll need to collect ${formatAmount(shortfall)} before payroll to maintain your safety buffer.`;
    } else if (bufferAfter && bufferAfter < 50000) {
      return `Cash position after payroll will be tight. Consider accelerating collections or reviewing non-essential expenses.`;
    }
  }

  // Buffer/runway insights
  if (title.includes('buffer') || title.includes('runway')) {
    const bufferPercent = context.buffer_percent as number;
    const monthlyBurn = context.monthly_burn as number;

    if (bufferPercent && bufferPercent < 50) {
      return `Your cash buffer is critically low. Focus on accelerating revenue collection and reviewing discretionary expenses.`;
    } else if (monthlyBurn) {
      return `At current burn rate of ${formatAmount(monthlyBurn)}/month, you have limited flexibility for unexpected expenses.`;
    }
  }

  // Tax/statutory insights
  if (title.includes('tax') || context.obligation_type?.toString().includes('Tax')) {
    const reserveBalance = context.reserve_balance as number;
    const amount = context.amount as number;

    if (reserveBalance && amount && reserveBalance >= amount) {
      return `Your tax reserve has sufficient funds. Ensure payment is scheduled before the deadline to avoid penalties.`;
    } else if (reserveBalance && amount && reserveBalance < amount) {
      return `Tax reserve is short by ${formatAmount(amount - reserveBalance)}. Transfer funds to ensure timely payment.`;
    }
  }

  // Expense variance insights
  if (title.includes('expense') && title.includes('spike')) {
    const variancePercent = context.variance_percent as number;
    const bucketName = context.bucket_name as string;

    if (variancePercent && variancePercent > 50) {
      return `${bucketName || 'This expense'} has increased significantly. Review recent charges for unexpected costs.`;
    }
  }

  // Default to recommendation name if available
  return recommendation?.name || 'Review this alert and take appropriate action.';
}

/**
 * Generate suggested actions based on detection type and context
 */
function getSuggestedActions(item: DecisionItem): Array<{
  icon: 'email' | 'phone' | 'invoice' | 'transfer' | 'schedule' | 'review';
  label: string;
  description?: string;
  primary?: boolean;
}> {
  const actions: Array<{
    icon: 'email' | 'phone' | 'invoice' | 'transfer' | 'schedule' | 'review';
    label: string;
    description?: string;
    primary?: boolean;
  }> = [];

  // If we have a recommendation from the backend, show ONLY that action
  // This is the prepared action that Tamio has created specifically for this alert
  if (item.recommendation) {
    // Determine icon based on action type hints in the name
    const recName = item.recommendation.name.toLowerCase();
    let icon: 'email' | 'phone' | 'invoice' | 'transfer' | 'schedule' | 'review' = 'review';
    if (recName.includes('send') || recName.includes('reminder') || recName.includes('email')) {
      icon = 'email';
    } else if (recName.includes('call') || recName.includes('phone')) {
      icon = 'phone';
    } else if (recName.includes('invoice') || recName.includes('accelerate')) {
      icon = 'invoice';
    } else if (recName.includes('sweep') || recName.includes('transfer') || recName.includes('defer')) {
      icon = 'transfer';
    } else if (recName.includes('schedule')) {
      icon = 'schedule';
    } else if (recName.includes('reduce') || recName.includes('cancel')) {
      icon = 'review';
    }

    actions.push({
      icon,
      label: item.recommendation.name,
      description: item.recommendation.why_it_exists,
      primary: true,
    });

    return actions;
  }

  // Only generate generic actions if no backend recommendation exists
  const context = (item.alert as { context_data?: ContextData }).context_data || {};
  const title = item.alert.title.toLowerCase();

  // Late payment / overdue invoice actions
  if (title.includes('overdue') || title.includes('late payment')) {
    const daysOverdue = context.days_overdue as number;
    const clientName = context.client_name as string;

    if (daysOverdue && daysOverdue >= 14) {
      actions.push({
        icon: 'phone',
        label: `Call ${clientName || 'client'} directly`,
        description: 'Personal outreach for urgent follow-up',
        primary: true,
      });
    } else {
      actions.push({
        icon: 'email',
        label: 'Send payment reminder',
        description: `Follow-up for ${formatAmount(context.invoice_amount as number)}`,
        primary: true,
      });
    }
  }

  // Payroll safety actions
  else if (title.includes('payroll')) {
    const shortfall = context.shortfall as number;

    if (shortfall && shortfall > 0) {
      actions.push({
        icon: 'email',
        label: 'Accelerate collections',
        description: 'Contact clients with outstanding payments',
        primary: true,
      });
    } else {
      actions.push({
        icon: 'review',
        label: 'Confirm payroll run',
        description: 'Verify amounts and approve',
        primary: true,
      });
    }
  }

  // Tax/statutory deadline actions
  else if (title.includes('tax') || context.obligation_type?.toString().includes('Tax')) {
    actions.push({
      icon: 'schedule',
      label: 'Schedule payment',
      description: 'Set up payment before deadline',
      primary: true,
    });
  }

  // Buffer/runway alerts
  else if (title.includes('buffer') || title.includes('runway')) {
    actions.push({
      icon: 'email',
      label: 'Accelerate collections',
      description: 'Follow up on outstanding invoices',
      primary: true,
    });
  }

  // Default action if nothing matched
  if (actions.length === 0) {
    actions.push({
      icon: 'review',
      label: 'Review and take action',
      description: 'Assess the situation and respond',
      primary: true,
    });
  }

  return actions;
}

const ActionIcon = ({ type }: { type: string }) => {
  switch (type) {
    case 'email':
      return <Mail className="w-4 h-4" />;
    case 'phone':
      return <Phone className="w-4 h-4" />;
    case 'invoice':
      return <FileText className="w-4 h-4" />;
    case 'transfer':
      return <ArrowDownRight className="w-4 h-4" />;
    case 'schedule':
      return <Calendar className="w-4 h-4" />;
    case 'review':
      return <AlertTriangle className="w-4 h-4" />;
    default:
      return <FileText className="w-4 h-4" />;
  }
};

const EntityIcon = ({ type }: { type: string | null }) => {
  switch (type) {
    case 'client':
      return <User className="w-3 h-3" />;
    case 'expense':
    case 'vendor':
      return <Receipt className="w-3 h-3" />;
    case 'payroll':
      return <Users className="w-3 h-3" />;
    case 'tax':
      return <Building2 className="w-3 h-3" />;
    default:
      return <DollarSign className="w-3 h-3" />;
  }
};

const getEntityColors = (type: string | null): string => {
  switch (type) {
    case 'client':
      return 'bg-blue-50 text-blue-700';
    case 'expense':
    case 'vendor':
      return 'bg-purple-50 text-purple-700';
    case 'payroll':
      return 'bg-emerald-50 text-emerald-700';
    case 'tax':
      return 'bg-amber-50 text-amber-700';
    default:
      return 'bg-gray-50 text-gray-700';
  }
};

// Type for custom actions added by user
interface CustomAction {
  id: string;
  label: string;
  description?: string;
}

export function DecisionCard({
  item,
  onApprove: _onApprove,
  onModify: _onModify,
  onDismiss,
  onChatWithTami,
  onRunScenario,
}: DecisionCardProps) {
  // Suppress unused variable warnings - these props are kept for API compatibility
  void _onApprove;
  void _onModify;
  const [isDismissing, setIsDismissing] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [customActionInput, setCustomActionInput] = useState('');
  const [customActions, setCustomActions] = useState<CustomAction[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when form opens
  useEffect(() => {
    if (showAddForm && inputRef.current) {
      inputRef.current.focus();
    }
  }, [showAddForm]);

  const handleAddCustomAction = () => {
    if (customActionInput.trim()) {
      const newAction: CustomAction = {
        id: `custom-${Date.now()}`,
        label: customActionInput.trim(),
      };
      setCustomActions([...customActions, newAction]);
      setCustomActionInput('');
      setShowAddForm(false);
    }
  };

  const handleRemoveCustomAction = (id: string) => {
    setCustomActions(customActions.filter(a => a.id !== id));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddCustomAction();
    } else if (e.key === 'Escape') {
      setShowAddForm(false);
      setCustomActionInput('');
    }
  };

  const { alert, recommendation } = item;
  const severityStyles = getSeverityStyles(alert.severity);
  const linkedEntity = getLinkedEntity(item);
  const suggestedActions = getSuggestedActions(item);
  const insightText = getInsightText(item);

  // Severity-based background colors (faded)
  const severityBgClass = {
    urgent: 'bg-tomato/5',
    high: 'bg-amber-500/5',
    normal: 'bg-lime/5',
  }[alert.severity];

  const handleDismiss = async () => {
    setIsDismissing(true);
    try {
      await onDismiss(alert.id);
    } finally {
      setIsDismissing(false);
    }
  };

  // Format impact text with more context
  const context = (alert as { context_data?: ContextData }).context_data || {};
  const impactText = alert.buffer_impact_percent
    ? `${alert.buffer_impact_percent}% of buffer at risk${alert.cash_impact ? ` (${formatAmount(alert.cash_impact)} shortfall)` : ''}`
    : alert.cash_impact
      ? `${formatAmount(Math.abs(alert.cash_impact))} ${alert.cash_impact < 0 ? 'impact' : 'at stake'}`
      : null;

  // Get additional context for display
  const daysOverdue = context.days_overdue as number;
  const avgDelayDays = context.avg_delay_days as number;
  const paymentBehavior = context.payment_behavior as string;

  return (
    <div
      className={cn(
        'relative rounded-xl',
        'backdrop-blur-sm',
        'border border-white/50',
        'shadow-lg shadow-black/5',
        severityBgClass
      )}
    >
      <div className="p-4 sm:p-5">
        {/* Header with Title and Dismiss Button */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-base font-bold text-gunmetal leading-snug">
            {alert.title}
          </h3>
          <button
            onClick={handleDismiss}
            disabled={isDismissing}
            className="flex-shrink-0 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-50"
            title="Dismiss Alert"
          >
            {isDismissing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <X className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Insight - contextual explanation */}
        <p className="text-sm text-gray-600 leading-relaxed mb-3">
          {insightText}
        </p>

        {/* Impact & Context - secondary info */}
        <div className="text-sm text-gray-500 mb-3 space-y-1">
          {impactText && (
            <p className="flex items-center gap-1.5">
              <Wallet className="w-3.5 h-3.5 text-gray-400" />
              {impactText}
            </p>
          )}
          {alert.primary_driver && (
            <p className="flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-gray-400" />
              {alert.primary_driver}
            </p>
          )}
          {/* Show payment pattern insight for late payments */}
          {daysOverdue && avgDelayDays && (
            <p className="text-xs text-gray-400 italic">
              {daysOverdue > avgDelayDays
                ? `${daysOverdue - avgDelayDays} days beyond their typical ${avgDelayDays}-day delay`
                : paymentBehavior === 'delayed'
                  ? `Within their usual ${avgDelayDays}-day payment pattern`
                  : null
              }
            </p>
          )}
        </div>

        {/* Tags row: Linked entity + Urgency + Due date */}
        <div className="flex items-center gap-2 flex-wrap mb-4">
          {/* Linked entity pill */}
          {linkedEntity.type && linkedEntity.name && (
            <span className={cn(
              'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
              getEntityColors(linkedEntity.type)
            )}>
              <EntityIcon type={linkedEntity.type} />
              {linkedEntity.name}
            </span>
          )}

          {/* Urgency tag */}
          <span
            className={cn(
              'px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wide',
              severityStyles.bgClass,
              severityStyles.textClass
            )}
          >
            {alert.severity}
          </span>

          {/* Due date tag */}
          {alert.due_horizon_label && alert.due_horizon_label !== 'No deadline' && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
              <Clock className="w-3 h-3" />
              {alert.due_horizon_label}
            </span>
          )}
        </div>

        {/* Suggested Actions Section */}
        {suggestedActions.length > 0 && (
          <div className="bg-white/60 rounded-lg p-4 mb-4 border border-gray-100">
            <h4 className="text-sm font-semibold text-gunmetal mb-3">
              Recommended Actions
            </h4>

            {/* Action items */}
            <div className="space-y-2 mb-3">
              {suggestedActions.map((action, index) => (
                <div
                  key={index}
                  className={cn(
                    'flex items-center gap-3 p-2.5 rounded-lg',
                    action.primary
                      ? 'bg-blue-50/80 border border-blue-100'
                      : 'bg-gray-50 border border-gray-100'
                  )}
                >
                  <div className={cn(
                    'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                    action.primary
                      ? 'bg-blue-100 text-blue-600'
                      : 'bg-gray-200 text-gray-500'
                  )}>
                    <ActionIcon type={action.icon} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={cn(
                      'text-sm font-medium',
                      action.primary ? 'text-blue-900' : 'text-gunmetal'
                    )}>
                      {action.label}
                      {action.primary && (
                        <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded uppercase font-semibold">
                          Recommended
                        </span>
                      )}
                    </p>
                    {action.description && (
                      <p className="text-xs text-gray-500 truncate">{action.description}</p>
                    )}
                  </div>
                </div>
              ))}

              {/* Custom actions added by user */}
              {customActions.map((action) => (
                <div
                  key={action.id}
                  className="flex items-center gap-3 p-2.5 rounded-lg bg-emerald-50/80 border border-emerald-100"
                >
                  <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-emerald-100 text-emerald-600">
                    <Check className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-emerald-900">
                      {action.label}
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-emerald-100 text-emerald-600 rounded uppercase font-semibold">
                        Custom
                      </span>
                    </p>
                  </div>
                  <button
                    onClick={() => handleRemoveCustomAction(action.id)}
                    className="p-1 rounded text-emerald-400 hover:text-emerald-600 hover:bg-emerald-100 transition-colors"
                    title="Remove action"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}

              {/* Inline add custom action form */}
              {showAddForm && (
                <div className="flex items-center gap-2 p-2.5 rounded-lg bg-gray-50 border border-gray-200">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-gray-200 text-gray-500">
                    <Plus className="w-4 h-4" />
                  </div>
                  <input
                    ref={inputRef}
                    type="text"
                    value={customActionInput}
                    onChange={(e) => setCustomActionInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Describe your action..."
                    className="flex-1 text-sm bg-transparent border-none outline-none placeholder:text-gray-400"
                  />
                  <button
                    onClick={handleAddCustomAction}
                    disabled={!customActionInput.trim()}
                    className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Add action"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => {
                      setShowAddForm(false);
                      setCustomActionInput('');
                    }}
                    className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                    title="Cancel"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>

            {/* Alternative options */}
            <div className="flex items-center gap-2 pt-3 border-t border-gray-200 flex-wrap">
              {!showAddForm && (
                <button
                  onClick={() => setShowAddForm(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add custom action
                </button>
              )}
              {onChatWithTami && (
                <button
                  onClick={() => onChatWithTami(item)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                >
                  <MessageCircle className="w-3.5 h-3.5" />
                  Chat with TAMI
                </button>
              )}
              {onRunScenario && (
                <button
                  onClick={() => onRunScenario(item)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                >
                  <TrendingUp className="w-3.5 h-3.5" />
                  Run Scenario
                </button>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
