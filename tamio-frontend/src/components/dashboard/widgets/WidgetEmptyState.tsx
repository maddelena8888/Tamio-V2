/**
 * Widget Empty State - No-data state for dashboard widgets
 */

import { Link } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface WidgetEmptyStateProps {
  /** Message to display */
  message: string;
  /** Optional action link */
  actionLabel?: string;
  actionHref?: string;
  /** Icon to display (defaults to AlertCircle) */
  icon?: React.ReactNode;
  className?: string;
}

export function WidgetEmptyState({
  message,
  actionLabel,
  actionHref,
  icon,
  className,
}: WidgetEmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-6 text-center',
        className
      )}
    >
      <div className="text-muted-foreground/50">
        {icon ?? <AlertCircle className="w-8 h-8" />}
      </div>
      <p className="text-sm text-muted-foreground max-w-[200px]">{message}</p>
      {actionLabel && actionHref && (
        <Link
          to={actionHref}
          className="text-sm text-gunmetal hover:underline font-medium"
        >
          {actionLabel} &rarr;
        </Link>
      )}
    </div>
  );
}
