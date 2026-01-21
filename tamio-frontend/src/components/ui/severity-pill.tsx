import { cn } from '@/lib/utils';

type Severity = 'urgent' | 'high' | 'normal';

interface SeverityPillProps {
  severity: Severity;
  className?: string;
}

const severityStyles: Record<Severity, { label: string; classes: string }> = {
  urgent: {
    label: 'Urgent',
    classes: 'bg-tomato/10 text-tomato border-tomato/20',
  },
  high: {
    label: 'High',
    classes: 'bg-yellow-500/10 text-yellow-700 border-yellow-500/20',
  },
  normal: {
    label: 'Medium',
    classes: 'bg-lime/10 text-lime-700 border-lime/20',
  },
};

export function SeverityPill({ severity, className }: SeverityPillProps) {
  const config = severityStyles[severity] || severityStyles.normal;

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-full',
        'text-[10px] font-semibold uppercase tracking-wide',
        'border backdrop-blur-sm',
        config.classes,
        className
      )}
    >
      {config.label}
    </span>
  );
}
