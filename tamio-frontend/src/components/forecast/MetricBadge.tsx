import { cn } from '@/lib/utils';
import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import type { MetricStatus } from '@/lib/api/types';

interface MetricBadgeProps {
  label: string;
  value: string;
  unit?: string | null;
  status: MetricStatus;
  icon?: string;
  className?: string;
}

const statusConfig: Record<MetricStatus, { bg: string; text: string; Icon: typeof CheckCircle2 }> = {
  good: {
    bg: 'bg-lime/20',
    text: 'text-lime-dark',
    Icon: CheckCircle2,
  },
  warning: {
    bg: 'bg-amber-100',
    text: 'text-amber-600',
    Icon: AlertTriangle,
  },
  critical: {
    bg: 'bg-tomato/20',
    text: 'text-tomato',
    Icon: XCircle,
  },
};

export function MetricBadge({ label, value, unit, status, className }: MetricBadgeProps) {
  const config = statusConfig[status];
  const Icon = config.Icon;

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 px-4 py-2.5 rounded-xl',
        'bg-white shadow-sm border border-white/40',
        'backdrop-blur-sm',
        className
      )}
    >
      <Icon className={cn('h-4 w-4', config.text)} />
      <span className="text-sm font-medium text-gunmetal">
        {label}: {value}
        {unit && <span className="text-gunmetal/70">{unit}</span>}
      </span>
    </div>
  );
}

export default MetricBadge;
