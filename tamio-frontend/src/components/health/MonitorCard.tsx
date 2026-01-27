import { ArrowRight, Check, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { MonitorData, MonitorStatus } from '@/lib/api/health';

// ============================================================================
// Types
// ============================================================================

export interface MonitorCardProps {
  /** Card title (e.g., "CASH HEALTH", "BURN RATE") */
  title: string;
  /** Monitor data from API */
  data: MonitorData;
  /** Click handler for navigation */
  onClick?: () => void;
  /** Additional class names */
  className?: string;
}

// ============================================================================
// Helpers
// ============================================================================

function StatusBadge({ status }: { status: MonitorStatus }) {
  const isHealthy = status === 'healthy';

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        isHealthy
          ? 'bg-lime/20 text-lime-700'
          : 'bg-amber-100 text-amber-700'
      )}
    >
      {isHealthy ? (
        <Check className="w-3 h-3" />
      ) : (
        <AlertTriangle className="w-3 h-3" />
      )}
      {isHealthy ? 'HEALTHY' : 'WATCH'}
    </span>
  );
}

// ============================================================================
// Component
// ============================================================================

export function MonitorCard({
  title,
  data,
  onClick,
  className,
}: MonitorCardProps) {
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
        {/* Left side: title, value, trend */}
        <div className="flex flex-col gap-1">
          {/* Title row with status badge */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {title}
            </span>
            <StatusBadge status={data.status} />
          </div>

          {/* Value */}
          <span className="text-xl font-semibold text-gunmetal">
            {data.formatted}
          </span>

          {/* Trend */}
          <span className="text-xs text-muted-foreground">
            Current position &bull; {data.trend_label}
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

export default MonitorCard;
