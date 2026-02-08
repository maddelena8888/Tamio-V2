/**
 * AlertsPanelSummaryBar Component
 *
 * Compact summary bar showing alert counts and totals for the dashboard panel.
 * Based on DecisionQueueSummaryBar but optimized for dashboard placement.
 */

import { RefreshCw, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { formatAmount } from '@/lib/utils/decisionQueue';
import type { AlertPanelSummary } from './types';

interface AlertsPanelSummaryBarProps {
  summary: AlertPanelSummary;
  isLoading: boolean;
  onRefresh: () => void;
  onViewAll: () => void;
}

interface SummaryItemProps {
  count: number;
  label: string;
  sublabel: string;
  dotColor: string;
}

function SummaryItem({ count, label, sublabel, dotColor }: SummaryItemProps) {
  return (
    <div className="flex items-center gap-2">
      {/* Colored dot */}
      <div className={cn('w-2.5 h-2.5 rounded-full', dotColor)} />

      {/* Count badge */}
      <span className="text-lg font-semibold text-gunmetal">{count}</span>

      {/* Labels */}
      <div className="flex flex-col">
        <span className="text-sm font-medium text-gunmetal leading-tight">{label}</span>
        <span className="text-xs text-gray-500 leading-tight">{sublabel}</span>
      </div>
    </div>
  );
}

export function AlertsPanelSummaryBar({
  summary,
  isLoading,
  onRefresh,
  onViewAll,
}: AlertsPanelSummaryBarProps) {
  const { requiresDecision, beingHandled, monitoring } = summary;

  // Format sublabels
  const decisionSublabel =
    requiresDecision.totalAtRisk > 0
      ? `${formatAmount(requiresDecision.totalAtRisk)} at risk`
      : 'No risk';

  const handlingSublabel = beingHandled.hasExecuting
    ? 'In progress'
    : 'None executing';

  const monitoringSublabel =
    monitoring.totalUpcoming > 0
      ? `${formatAmount(monitoring.totalUpcoming)} upcoming`
      : 'No upcoming';

  return (
    <div className="flex items-center justify-between flex-wrap gap-4 pb-4 border-b border-gray-100">
      {/* Summary items */}
      <div className="flex items-center gap-6 flex-wrap">
        {/* Requires Decision */}
        <SummaryItem
          count={requiresDecision.count}
          label="Require Decision"
          sublabel={decisionSublabel}
          dotColor="bg-tomato"
        />

        {/* Divider */}
        <div className="hidden sm:block w-px h-8 bg-gray-200" />

        {/* Being Handled */}
        <SummaryItem
          count={beingHandled.count}
          label="Being Handled"
          sublabel={handlingSublabel}
          dotColor="bg-blue-500"
        />

        {/* Divider */}
        <div className="hidden sm:block w-px h-8 bg-gray-200" />

        {/* Monitoring */}
        <SummaryItem
          count={monitoring.count}
          label="Monitoring"
          sublabel={monitoringSublabel}
          dotColor="bg-lime"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={onRefresh}
          disabled={isLoading}
          className="text-gray-400 hover:text-gunmetal h-8 w-8"
        >
          <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
        </Button>

        <Button
          variant="ghost"
          size="sm"
          onClick={onViewAll}
          className="text-gray-600 hover:text-gunmetal gap-1.5"
        >
          View All
          <ExternalLink className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}
