/**
 * Health Status Widget
 *
 * Shows overall health status - "On Track" or "Action Needed" banner
 * with the single most critical alert if any exists.
 */

import { Link } from 'react-router-dom';
import { CheckCircle, AlertTriangle, AlertCircle } from 'lucide-react';
import { useWidgetData } from '@/hooks/useDashboardData';
import { cn } from '@/lib/utils';
import { WidgetSkeleton } from './WidgetSkeleton';
import { WidgetEmptyState } from './WidgetEmptyState';
import type { WidgetProps } from './types';

export function HealthStatusWidget({ className }: WidgetProps) {
  const { healthData, isLoading } = useWidgetData();

  if (isLoading) {
    return <WidgetSkeleton className={className} />;
  }

  if (!healthData) {
    return (
      <WidgetEmptyState
        message="Connect a data source to see your health status"
        actionLabel="Set up data"
        actionHref="/settings/data"
        className={className}
      />
    );
  }

  // Determine overall status from health metrics
  const { runway, liquidity, cash_velocity, critical_alerts } = healthData;
  const hasCritical =
    runway.status === 'critical' ||
    liquidity.status === 'critical' ||
    cash_velocity.status === 'critical' ||
    critical_alerts.length > 0;
  const hasWarning =
    runway.status === 'warning' ||
    liquidity.status === 'warning' ||
    cash_velocity.status === 'warning';

  const overallStatus: 'good' | 'warning' | 'critical' = hasCritical
    ? 'critical'
    : hasWarning
      ? 'warning'
      : 'good';

  const topAlert = critical_alerts[0];

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Status Banner */}
      <div
        className={cn(
          'flex-1 flex flex-col items-center justify-center rounded-xl py-4 px-3',
          overallStatus === 'good' && 'bg-lime/10',
          overallStatus === 'warning' && 'bg-amber-50',
          overallStatus === 'critical' && 'bg-tomato/10'
        )}
      >
        {/* Icon */}
        <div className="mb-2">
          {overallStatus === 'good' && (
            <CheckCircle className="w-10 h-10 text-lime-600" />
          )}
          {overallStatus === 'warning' && (
            <AlertTriangle className="w-10 h-10 text-amber-500" />
          )}
          {overallStatus === 'critical' && (
            <AlertCircle className="w-10 h-10 text-tomato" />
          )}
        </div>

        {/* Status Text */}
        <span
          className={cn(
            'text-xl font-bold',
            overallStatus === 'good' && 'text-lime-700',
            overallStatus === 'warning' && 'text-amber-700',
            overallStatus === 'critical' && 'text-tomato'
          )}
        >
          {overallStatus === 'good' && 'On Track'}
          {overallStatus === 'warning' && 'Needs Attention'}
          {overallStatus === 'critical' && 'Action Needed'}
        </span>

        {/* Alert Summary */}
        {topAlert && (
          <p className="text-xs text-muted-foreground mt-2 text-center line-clamp-2 max-w-[180px]">
            {topAlert.title}
          </p>
        )}
      </div>

      {/* Action Link */}
      {critical_alerts.length > 0 && (
        <div className="flex justify-center pt-3">
          <Link to="/health" className="text-xs text-gunmetal hover:underline">
            View {critical_alerts.length} alert{critical_alerts.length !== 1 ? 's' : ''} &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}
