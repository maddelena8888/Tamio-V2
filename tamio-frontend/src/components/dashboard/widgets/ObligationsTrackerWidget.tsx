/**
 * Obligations Tracker Widget
 *
 * Shows upcoming 30 days of obligations: Payroll, VAT, Supplier payments.
 * Nothing falls through the cracks.
 */

import { Link } from 'react-router-dom';
import { CheckCircle, AlertTriangle, AlertCircle, Calendar } from 'lucide-react';
import { useWidgetData } from '@/hooks/useDashboardData';
import { cn } from '@/lib/utils';
import { WidgetSkeleton } from './WidgetSkeleton';
import { WidgetEmptyState } from './WidgetEmptyState';
import type { WidgetProps } from './types';

export function ObligationsTrackerWidget({ className }: WidgetProps) {
  const { healthData, isLoading } = useWidgetData();

  if (isLoading) {
    return <WidgetSkeleton className={className} />;
  }

  if (!healthData) {
    return (
      <WidgetEmptyState
        message="Connect a data source to track obligations"
        actionLabel="Set up data"
        actionHref="/settings/data"
        className={className}
      />
    );
  }

  const { obligations_health } = healthData;
  const { covered_count, total_count, status, buffer_percentage } = obligations_health;

  // Status styling
  const statusConfig = {
    covered: {
      icon: CheckCircle,
      label: 'Covered',
      bgClass: 'bg-lime/20',
      textClass: 'text-lime-700',
      iconClass: 'text-lime-600',
    },
    tight: {
      icon: AlertTriangle,
      label: 'Tight',
      bgClass: 'bg-amber-100',
      textClass: 'text-amber-700',
      iconClass: 'text-amber-500',
    },
    at_risk: {
      icon: AlertCircle,
      label: 'At Risk',
      bgClass: 'bg-tomato/20',
      textClass: 'text-tomato',
      iconClass: 'text-tomato',
    },
  };

  const config = statusConfig[status];
  const StatusIcon = config.icon;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Next 30 Days
          </span>
        </div>
        <span
          className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
            config.bgClass,
            config.textClass
          )}
        >
          <StatusIcon className={cn('w-3 h-3', config.iconClass)} />
          {config.label}
        </span>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col justify-center">
        {/* Coverage Ratio */}
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-gunmetal">{covered_count}</span>
          <span className="text-lg text-muted-foreground">of {total_count}</span>
        </div>
        <span className="text-sm text-muted-foreground">obligations covered</span>

        {/* Progress Bar */}
        <div className="mt-3 h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              status === 'covered' && 'bg-lime',
              status === 'tight' && 'bg-amber-400',
              status === 'at_risk' && 'bg-tomato'
            )}
            style={{ width: `${Math.min((covered_count / total_count) * 100, 100)}%` }}
          />
        </div>

        {/* Buffer Info */}
        <div className="mt-2 text-xs text-muted-foreground">
          {buffer_percentage > 0 ? (
            <span>
              <span className={status === 'covered' ? 'text-lime-700 font-medium' : ''}>
                {buffer_percentage.toFixed(0)}%
              </span>{' '}
              buffer available
            </span>
          ) : (
            <span className="text-tomato">No buffer remaining</span>
          )}
        </div>
      </div>

      {/* Action Link */}
      <div className="flex justify-center pt-3">
        <Link to="/obligations" className="text-xs text-gunmetal hover:underline">
          View all obligations &rarr;
        </Link>
      </div>
    </div>
  );
}
