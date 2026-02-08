/**
 * Net Cash Flow Widget
 *
 * Shows money in vs money out for the period.
 * Pattern recognition for cash flow trends.
 */

import { Link } from 'react-router-dom';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import { useWidgetData } from '@/hooks/useDashboardData';
import { cn } from '@/lib/utils';
import { WidgetSkeleton } from './WidgetSkeleton';
import { WidgetEmptyState } from './WidgetEmptyState';
import type { WidgetProps } from './types';
import type { ForecastWeek } from '@/lib/api/types';

export function NetCashFlowWidget({ className }: WidgetProps) {
  const { forecastData, isLoading } = useWidgetData();

  if (isLoading) {
    return <WidgetSkeleton className={className} />;
  }

  if (!forecastData) {
    return (
      <WidgetEmptyState
        message="Connect a data source to see cash flow"
        actionLabel="Set up data"
        actionHref="/settings/data"
        className={className}
      />
    );
  }

  // Calculate totals from forecast weeks
  const { weeks, summary } = forecastData;

  // Get this month's totals from the first 4 weeks or summary
  const totalInflows = summary?.total_cash_in
    ? parseFloat(summary.total_cash_in)
    : weeks.slice(0, 4).reduce((sum: number, week: ForecastWeek) => sum + parseFloat(week.cash_in || '0'), 0);

  const totalOutflows = summary?.total_cash_out
    ? parseFloat(summary.total_cash_out)
    : weeks.slice(0, 4).reduce((sum: number, week: ForecastWeek) => sum + parseFloat(week.cash_out || '0'), 0);

  const netFlow = totalInflows - totalOutflows;
  const isPositive = netFlow >= 0;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
        This Month
      </span>

      {/* Flow Comparison */}
      <div className="flex-1 space-y-3">
        {/* Inflows */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ArrowUpRight className="w-4 h-4 text-lime-600" />
            <span className="text-sm text-muted-foreground">Money In</span>
          </div>
          <span className="text-sm font-semibold text-lime-700">
            {formatCurrency(totalInflows)}
          </span>
        </div>

        {/* Outflows */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ArrowDownRight className="w-4 h-4 text-tomato" />
            <span className="text-sm text-muted-foreground">Money Out</span>
          </div>
          <span className="text-sm font-semibold text-tomato">
            {formatCurrency(totalOutflows)}
          </span>
        </div>

        {/* Divider */}
        <div className="border-t border-white/20 pt-2">
          {/* Net Flow */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Minus className="w-4 h-4 text-gunmetal" />
              <span className="text-sm font-medium text-gunmetal">Net Flow</span>
            </div>
            <span
              className={cn(
                'text-lg font-bold',
                isPositive ? 'text-lime-700' : 'text-tomato'
              )}
            >
              {isPositive ? '+' : ''}
              {formatCurrency(netFlow)}
            </span>
          </div>
        </div>
      </div>

      {/* Status Indicator */}
      <div className="flex justify-center pt-2">
        <span
          className={cn(
            'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium',
            isPositive ? 'bg-lime/20 text-lime-700' : 'bg-tomato/20 text-tomato'
          )}
        >
          {isPositive ? 'Cash Growing' : 'Cash Declining'}
        </span>
      </div>

      {/* Action Link */}
      <div className="flex justify-center pt-2">
        <Link to="/forecast" className="text-xs text-gunmetal hover:underline">
          View details &rarr;
        </Link>
      </div>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatCurrency(amount: number): string {
  const absAmount = Math.abs(amount);
  if (absAmount >= 1_000_000) {
    return `$${(amount / 1_000_000).toFixed(1)}M`.replace('.0M', 'M');
  } else if (absAmount >= 1_000) {
    return `$${Math.round(amount / 1_000).toLocaleString()}K`;
  }
  return `$${Math.round(amount).toLocaleString()}`;
}
