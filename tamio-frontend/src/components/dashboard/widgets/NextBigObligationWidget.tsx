/**
 * Next Big Obligation Widget
 *
 * Highlights the largest upcoming payment: "Payroll: $23,500 due in 8 days"
 * What's the next thing that could hurt us?
 */

import { Link } from 'react-router-dom';
import { Calendar, AlertTriangle, CheckCircle } from 'lucide-react';
import { useWidgetData } from '@/hooks/useDashboardData';
import { cn } from '@/lib/utils';
import { WidgetSkeleton } from './WidgetSkeleton';
import { WidgetEmptyState } from './WidgetEmptyState';
import type { WidgetProps } from './types';

export function NextBigObligationWidget({ className }: WidgetProps) {
  const { healthData, isLoading } = useWidgetData();

  if (isLoading) {
    return <WidgetSkeleton className={className} />;
  }

  if (!healthData) {
    return (
      <WidgetEmptyState
        message="Connect a data source to see obligations"
        actionLabel="Set up data"
        actionHref="/settings/data"
        className={className}
      />
    );
  }

  const { obligations_health } = healthData;
  const {
    next_obligation_name,
    next_obligation_amount_formatted,
    next_obligation_days,
    status,
  } = obligations_health;

  // No upcoming obligations
  if (!next_obligation_name || next_obligation_days === null) {
    return (
      <div className={cn('flex flex-col h-full items-center justify-center', className)}>
        <CheckCircle className="w-10 h-10 text-lime-600 mb-2" />
        <span className="text-lg font-semibold text-lime-700">All Clear</span>
        <span className="text-xs text-muted-foreground mt-1">
          No upcoming obligations
        </span>
      </div>
    );
  }

  // Determine urgency
  const isUrgent = next_obligation_days <= 7 && status === 'at_risk';
  const isSoon = next_obligation_days <= 14;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Icon and Title */}
      <div className="flex items-center gap-2 mb-3">
        <Calendar
          className={cn(
            'w-4 h-4',
            isUrgent ? 'text-tomato' : isSoon ? 'text-amber-500' : 'text-muted-foreground'
          )}
        />
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Next Obligation
        </span>
      </div>

      {/* Obligation Details */}
      <div className="flex-1 flex flex-col justify-center">
        {/* Name */}
        <span className="text-base font-semibold text-gunmetal line-clamp-1">
          {next_obligation_name}
        </span>

        {/* Amount */}
        <span
          className={cn(
            'text-2xl font-bold mt-1',
            isUrgent ? 'text-tomato' : 'text-gunmetal'
          )}
        >
          {next_obligation_amount_formatted}
        </span>

        {/* Due Date */}
        <div className="flex items-center gap-1.5 mt-2">
          {isUrgent && <AlertTriangle className="w-3.5 h-3.5 text-tomato" />}
          <span
            className={cn(
              'text-sm',
              isUrgent ? 'text-tomato font-medium' : 'text-muted-foreground'
            )}
          >
            Due in {next_obligation_days} day{next_obligation_days !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Status Badge */}
      <div className="flex justify-center pt-2">
        <span
          className={cn(
            'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium',
            status === 'covered' && 'bg-lime/20 text-lime-700',
            status === 'tight' && 'bg-amber-100 text-amber-700',
            status === 'at_risk' && 'bg-tomato/20 text-tomato'
          )}
        >
          {status === 'covered' && 'Covered'}
          {status === 'tight' && 'Tight'}
          {status === 'at_risk' && 'At Risk'}
        </span>
      </div>

      {/* Action Link */}
      <div className="flex justify-center pt-2">
        <Link to="/obligations" className="text-xs text-gunmetal hover:underline">
          View all obligations &rarr;
        </Link>
      </div>
    </div>
  );
}
