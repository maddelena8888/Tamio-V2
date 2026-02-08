/**
 * Cash Position Widget
 *
 * Shows current total cash across all accounts with trend vs last week/month.
 * Real-time understanding of cash.
 */

import { Link } from 'react-router-dom';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useWidgetData } from '@/hooks/useDashboardData';
import { cn } from '@/lib/utils';
import { WidgetSkeleton } from './WidgetSkeleton';
import { WidgetEmptyState } from './WidgetEmptyState';
import type { WidgetProps } from './types';

export function CashPositionWidget({ className }: WidgetProps) {
  const { cashPosition, forecastData, isLoading } = useWidgetData();

  if (isLoading) {
    return <WidgetSkeleton className={className} />;
  }

  if (!cashPosition && !forecastData) {
    return (
      <WidgetEmptyState
        message="Connect a bank account to see your cash position"
        actionLabel="Connect account"
        actionHref="/settings/data"
        className={className}
      />
    );
  }

  // Get total cash from cash position or forecast starting cash
  const totalCash = cashPosition?.total_starting_cash || forecastData?.starting_cash || '0';
  const formattedCash = formatCurrency(parseFloat(totalCash));

  // Calculate trend (mock for now - would come from API in real implementation)
  const trend = 12.5; // Positive percentage change
  const trendDirection = trend > 0 ? 'up' : trend < 0 ? 'down' : 'flat';

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Label */}
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
        Current Position
      </span>

      {/* Hero Metric */}
      <div className="flex-1 flex flex-col justify-center">
        <span className="text-3xl font-bold text-gunmetal">{formattedCash}</span>

        {/* Trend Indicator */}
        <div className="flex items-center gap-1.5 mt-2">
          {trendDirection === 'up' && (
            <>
              <TrendingUp className="w-4 h-4 text-lime-600" />
              <span className="text-sm text-lime-700 font-medium">+{trend}%</span>
            </>
          )}
          {trendDirection === 'down' && (
            <>
              <TrendingDown className="w-4 h-4 text-tomato" />
              <span className="text-sm text-tomato font-medium">{trend}%</span>
            </>
          )}
          {trendDirection === 'flat' && (
            <>
              <Minus className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">No change</span>
            </>
          )}
          <span className="text-xs text-muted-foreground">vs last week</span>
        </div>
      </div>

      {/* Account Summary */}
      {cashPosition && cashPosition.accounts.length > 0 && (
        <div className="pt-3 border-t border-white/20">
          <span className="text-xs text-muted-foreground">
            {cashPosition.accounts.length} account
            {cashPosition.accounts.length !== 1 ? 's' : ''} connected
          </span>
        </div>
      )}

      {/* Action Link */}
      <div className="flex justify-center pt-2">
        <Link to="/forecast" className="text-xs text-gunmetal hover:underline">
          View forecast &rarr;
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
