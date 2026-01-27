import { ArrowRight, Check, AlertTriangle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ReceivablesHealthData, ReceivablesStatus } from '@/lib/api/health';
import { getReceivablesStatusStyles } from '@/lib/api/health';

// ============================================================================
// Types
// ============================================================================

export interface ReceivablesCardProps {
  /** Receivables health data from API */
  data: ReceivablesHealthData;
  /** Click handler for navigation */
  onClick?: () => void;
  /** Additional class names */
  className?: string;
}

// ============================================================================
// Helpers
// ============================================================================

function StatusBadge({ status }: { status: ReceivablesStatus }) {
  const styles = getReceivablesStatusStyles(status);
  const IconComponent = status === 'healthy'
    ? Check
    : status === 'watch'
      ? AlertTriangle
      : AlertCircle;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        styles.bgClass,
        styles.textClass
      )}
    >
      <IconComponent className="w-3 h-3" />
      {styles.label}
    </span>
  );
}

// ============================================================================
// Component
// ============================================================================

export function ReceivablesCard({
  data,
  onClick,
  className,
}: ReceivablesCardProps) {
  return (
    <div
      className={cn(
        'glass-subtle rounded-2xl p-5 transition-all duration-200',
        onClick && 'cursor-pointer hover:bg-white/40',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className="flex items-start justify-between">
        {/* Left side: title, value, detail */}
        <div className="flex flex-col gap-1">
          {/* Title row with status badge */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              RECEIVABLES
            </span>
            <StatusBadge status={data.status} />
          </div>

          {/* Primary metric: overdue amount */}
          <span className="text-xl font-semibold text-gunmetal">
            {data.overdue_amount_formatted}
          </span>

          {/* Detail line: invoice counts and avg lateness */}
          <span className="text-xs text-muted-foreground">
            {data.overdue_count} of {data.total_outstanding_count} invoices
            {data.overdue_count > 0 && ` \u2022 Avg ${data.avg_days_late}d late`}
          </span>
        </div>

        {/* Right side: arrow */}
        {onClick && (
          <ArrowRight className="w-5 h-5 text-muted-foreground/40 mt-1" />
        )}
      </div>
    </div>
  );
}

export default ReceivablesCard;
