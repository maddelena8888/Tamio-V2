import { cn } from '@/lib/utils';
import type { TransactionStatus } from '@/lib/api/types';

interface StatusBadgeProps {
  status: TransactionStatus;
  className?: string;
}

const statusConfig: Record<TransactionStatus, { bg: string; text: string; label: string }> = {
  overdue: {
    bg: 'bg-tomato',
    text: 'text-white',
    label: 'Overdue',
  },
  due: {
    bg: 'bg-amber-400',
    text: 'text-gunmetal',
    label: 'Due',
  },
  expected: {
    bg: 'bg-gray-200',
    text: 'text-gunmetal',
    label: 'Expected',
  },
  received: {
    bg: 'bg-lime',
    text: 'text-gunmetal',
    label: 'Received',
  },
  paid: {
    bg: 'bg-lime',
    text: 'text-gunmetal',
    label: 'Paid',
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        config.bg,
        config.text,
        className
      )}
    >
      {config.label}
    </span>
  );
}

export default StatusBadge;
