/**
 * Cash Runway Widget
 *
 * Displays weeks of operation remaining at current burn rate.
 * The #1 question: "How long can we survive?"
 */

import { Link } from 'react-router-dom';
import { useWidgetData } from '@/hooks/useDashboardData';
import { getHealthStatusStyles } from '@/lib/api/health';
import { cn } from '@/lib/utils';
import { WidgetSkeleton } from './WidgetSkeleton';
import { WidgetEmptyState } from './WidgetEmptyState';
import type { WidgetProps } from './types';

export function CashRunwayWidget({ className }: WidgetProps) {
  const { healthData, isLoading } = useWidgetData();

  if (isLoading) {
    return <WidgetSkeleton className={className} />;
  }

  if (!healthData) {
    return (
      <WidgetEmptyState
        message="Connect a data source to see your runway"
        actionLabel="Set up data"
        actionHref="/settings/data"
        className={className}
      />
    );
  }

  const { runway } = healthData;
  const styles = getHealthStatusStyles(runway.status);

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Hero Metric */}
      <div className="flex-1 flex flex-col items-center justify-center">
        <span className={cn('text-4xl font-bold', styles.textColor)}>{runway.label}</span>
        <span className="text-sm text-muted-foreground mt-1">runway</span>
      </div>

      {/* Status Indicator */}
      <div className="flex justify-center mb-3">
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
            styles.bgColor,
            styles.textColor
          )}
        >
          <span
            className={cn(
              'w-1.5 h-1.5 rounded-full',
              runway.status === 'good' && 'bg-lime-600',
              runway.status === 'warning' && 'bg-amber-500',
              runway.status === 'critical' && 'bg-tomato'
            )}
          />
          {runway.status === 'good' && 'Healthy'}
          {runway.status === 'warning' && 'Attention'}
          {runway.status === 'critical' && 'Critical'}
        </span>
      </div>

      {/* Sublabel */}
      <p className="text-xs text-muted-foreground text-center">{runway.sublabel}</p>

      {/* Action Link */}
      <div className="flex justify-center pt-3">
        <Link to="/forecast" className="text-xs text-gunmetal hover:underline">
          View forecast &rarr;
        </Link>
      </div>
    </div>
  );
}
