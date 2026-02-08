import { cn } from '@/lib/utils';
import { CheckCircle, Clock, AlertTriangle, Sparkles } from 'lucide-react';
import type { ReconciliationStatus } from '@/lib/api/types';

interface ReconciliationStatusBadgeProps {
  status: ReconciliationStatus;
  className?: string;
  showIcon?: boolean;
}

const statusConfig: Record<ReconciliationStatus, {
  bg: string;
  text: string;
  label: string;
  icon: typeof CheckCircle;
}> = {
  reconciled: {
    bg: 'bg-lime',
    text: 'text-gunmetal',
    label: 'Reconciled',
    icon: CheckCircle,
  },
  pending: {
    bg: 'bg-amber-400',
    text: 'text-gunmetal',
    label: 'Pending Review',
    icon: Clock,
  },
  unmatched: {
    bg: 'bg-tomato/20',
    text: 'text-tomato',
    label: 'Unmatched',
    icon: AlertTriangle,
  },
  ai_suggested: {
    bg: 'bg-mimi-pink',
    text: 'text-gunmetal',
    label: 'AI Suggested',
    icon: Sparkles,
  },
};

export function ReconciliationStatusBadge({
  status,
  className,
  showIcon = true,
}: ReconciliationStatusBadgeProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium',
        config.bg,
        config.text,
        className
      )}
    >
      {showIcon && <Icon className="w-3 h-3" />}
      {config.label}
    </span>
  );
}

export default ReconciliationStatusBadge;
