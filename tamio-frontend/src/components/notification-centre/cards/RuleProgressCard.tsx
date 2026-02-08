import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { Wallet, Receipt, Users, FileText, TrendingUp, GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import { type Rule, type RuleType, getStatusStyles } from '@/lib/api/rules';
import type { DraggedNotificationItem } from '../NotificationCentreContext';

interface RuleProgress {
  rule: Rule;
  currentValue: number;
  thresholdValue: number;
  progressPercentage: number;
  status: 'healthy' | 'warning' | 'triggered' | 'paused';
  statusMessage: string;
}

interface RuleProgressCardProps {
  ruleProgress: RuleProgress;
}

const RULE_ICONS: Record<RuleType, typeof Wallet> = {
  cash_buffer: Wallet,
  tax_vat_reserve: Receipt,
  payroll: Users,
  receivables: FileText,
  unusual_activity: TrendingUp,
};

const statusLabels: Record<string, string> = {
  healthy: 'Healthy',
  warning: 'Warning',
  triggered: 'Triggered',
  paused: 'Paused',
};

export function RuleProgressCard({ ruleProgress }: RuleProgressCardProps) {
  const { rule, progressPercentage, status, statusMessage } = ruleProgress;
  const styles = getStatusStyles(status);
  const Icon = RULE_ICONS[rule.rule_type];

  const dragData: DraggedNotificationItem = {
    type: 'rule',
    id: rule.id,
    title: rule.name,
    description: statusMessage,
    context: {
      rule_type: rule.rule_type,
      status,
      progressPercentage,
      config: rule.config,
    },
  };

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `rule-${rule.id}`,
    data: dragData,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
  };

  // Clamp progress for display (0-100)
  const displayProgress = Math.min(Math.max(progressPercentage, 0), 100);
  // Show overflow indicator if exceeding 100%
  const isExceeding = progressPercentage > 100;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'relative p-3 rounded-xl border border-gray-100 bg-white transition-all group',
        isDragging && 'opacity-50 shadow-lg z-50'
      )}
    >
      {/* Drag handle */}
      <div
        {...listeners}
        {...attributes}
        className="absolute left-1 top-1/2 -translate-y-1/2 p-1 cursor-grab opacity-0 group-hover:opacity-100 transition-opacity text-gray-300 hover:text-gray-500"
      >
        <GripVertical className="w-4 h-4" />
      </div>

      <div className="pl-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center">
              <Icon className="h-4 w-4 text-gunmetal" />
            </div>
            <span className="text-sm font-medium text-gunmetal">{rule.name}</span>
          </div>

          {/* Status Badge */}
          <div
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
              styles.bgClass,
              styles.textClass
            )}
          >
            <div className={cn('w-1.5 h-1.5 rounded-full', styles.dotClass)} />
            {statusLabels[status]}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1.5">
          <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden relative">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                status === 'healthy' && 'bg-lime',
                status === 'warning' && 'bg-amber-500',
                status === 'triggered' && 'bg-tomato',
                status === 'paused' && 'bg-gray-400'
              )}
              style={{ width: `${displayProgress}%` }}
            />
            {/* Overflow indicator */}
            {isExceeding && (
              <div className="absolute right-0 top-0 h-full w-1 bg-lime-600 animate-pulse" />
            )}
          </div>

          <div className="flex justify-between items-center text-xs">
            <span className="text-muted-foreground">{statusMessage}</span>
            <span
              className={cn(
                'font-medium',
                status === 'healthy' && 'text-lime-700',
                status === 'warning' && 'text-amber-600',
                status === 'triggered' && 'text-tomato',
                status === 'paused' && 'text-gray-500'
              )}
            >
              {progressPercentage.toFixed(0)}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper to calculate progress for different rule types
export function calculateRuleProgress(
  rule: Rule,
  currentCash?: number,
  monthlyExpenses?: number
): RuleProgress {
  // If rule is paused, return paused status
  if (rule.status === 'paused') {
    return {
      rule,
      currentValue: 0,
      thresholdValue: 0,
      progressPercentage: 0,
      status: 'paused',
      statusMessage: 'Monitoring paused',
    };
  }

  // If we have evaluation data from the rule, use it
  if (rule.current_evaluation) {
    const evalStatus = rule.current_evaluation.status;
    const data = rule.current_evaluation.data || {};

    return {
      rule,
      currentValue: (data.current_value as number) || 0,
      thresholdValue: (data.threshold_value as number) || 100,
      progressPercentage: (data.progress_percentage as number) || 100,
      status: evalStatus,
      statusMessage: rule.current_evaluation.message,
    };
  }

  // Fallback: Calculate based on rule type
  switch (rule.rule_type) {
    case 'cash_buffer': {
      const config = rule.config as { threshold_amount?: number; days_of_expenses?: number };
      const threshold = config.threshold_amount || (monthlyExpenses || 10000) * (config.days_of_expenses || 30) / 30;
      const current = currentCash || threshold * 1.2; // Default to healthy if no data
      const percentage = (current / threshold) * 100;

      let status: 'healthy' | 'warning' | 'triggered' = 'healthy';
      if (percentage < 75) status = 'triggered';
      else if (percentage < 100) status = 'warning';

      return {
        rule,
        currentValue: current,
        thresholdValue: threshold,
        progressPercentage: percentage,
        status,
        statusMessage: percentage >= 100
          ? `${percentage.toFixed(0)}% of buffer maintained`
          : `${(100 - percentage).toFixed(0)}% below target`,
      };
    }

    default:
      // For other rule types, use a generic calculation
      return {
        rule,
        currentValue: 100,
        thresholdValue: 100,
        progressPercentage: 100,
        status: 'healthy',
        statusMessage: 'Monitoring active',
      };
  }
}
