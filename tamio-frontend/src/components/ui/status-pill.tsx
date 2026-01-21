import { cn } from '@/lib/utils';

type ActionStatus = 'pending' | 'in_progress' | 'approved' | 'completed';

interface StatusPillProps {
  status: ActionStatus;
  className?: string;
}

const statusStyles: Record<ActionStatus, { label: string; classes: string; showDot: boolean }> = {
  pending: {
    label: 'Pending',
    classes: 'bg-gray-100 text-gray-600 border-gray-200',
    showDot: false,
  },
  in_progress: {
    label: 'In progress',
    classes: 'bg-blue-50 text-blue-600 border-blue-100',
    showDot: true,
  },
  approved: {
    label: 'Approved',
    classes: 'bg-lime/10 text-lime-700 border-lime/20',
    showDot: false,
  },
  completed: {
    label: 'Completed',
    classes: 'bg-gray-50 text-gray-400 border-gray-100',
    showDot: false,
  },
};

export function StatusPill({ status, className }: StatusPillProps) {
  const config = statusStyles[status] || statusStyles.pending;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full',
        'text-[10px] font-medium border',
        config.classes,
        className
      )}
    >
      {config.showDot && (
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
      )}
      {config.label}
    </span>
  );
}
