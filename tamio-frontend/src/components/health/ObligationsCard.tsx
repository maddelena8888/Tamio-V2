import { ArrowRight, Check, AlertTriangle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ObligationsHealthData, ObligationsStatus } from '@/lib/api/health';
import { getObligationsStatusStyles } from '@/lib/api/health';

// ============================================================================
// Types
// ============================================================================

export interface ObligationsCardProps {
  /** Obligations health data from API */
  data: ObligationsHealthData;
  /** Click handler for navigation */
  onClick?: () => void;
  /** Additional class names */
  className?: string;
}

// ============================================================================
// Helpers
// ============================================================================

function StatusBadge({ status }: { status: ObligationsStatus }) {
  const styles = getObligationsStatusStyles(status);
  const IconComponent = status === 'covered'
    ? Check
    : status === 'tight'
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

export function ObligationsCard({
  data,
  onClick,
  className,
}: ObligationsCardProps) {
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
              OBLIGATIONS
            </span>
            <StatusBadge status={data.status} />
          </div>

          {/* Primary metric: X of Y due */}
          <span className="text-xl font-semibold text-gunmetal">
            {data.covered_count} of {data.total_count} due
          </span>

          {/* Detail line: Next obligation */}
          {data.next_obligation_name ? (
            <span className="text-xs text-muted-foreground">
              Next: {data.next_obligation_name} {data.next_obligation_amount_formatted} in {data.next_obligation_days}d
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">
              No upcoming obligations
            </span>
          )}
        </div>

        {/* Right side: arrow */}
        {onClick && (
          <ArrowRight className="w-5 h-5 text-muted-foreground/40 mt-1" />
        )}
      </div>
    </div>
  );
}

export default ObligationsCard;
