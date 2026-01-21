/**
 * DecisionQueueSummaryBar Component
 *
 * Displays a horizontal summary bar at the top of the Decision Queue page.
 * Shows counts and totals for each section:
 * - Requires Decision: count + total at risk
 * - Being Handled: count + executing status
 * - Monitoring: count + upcoming total
 */

import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { NeuroCard } from '@/components/ui/neuro-card';
import type { DecisionQueueSummary } from '@/lib/api/alertsActions';
import { formatAmount } from '@/lib/utils/decisionQueue';

interface DecisionQueueSummaryBarProps {
  summary: DecisionQueueSummary;
  isLoading: boolean;
  onRefresh: () => void;
}

interface SummaryItemProps {
  count: number;
  label: string;
  sublabel: string;
  badgeColor: string;
}

function SummaryItem({ count, label, sublabel, badgeColor }: SummaryItemProps) {
  return (
    <div className="flex items-center gap-3">
      {/* Colored badge with count */}
      <div
        className={cn(
          'w-10 h-10 rounded-full flex items-center justify-center',
          'text-lg font-bold',
          badgeColor
        )}
      >
        {count}
      </div>

      {/* Labels */}
      <div className="flex flex-col">
        <span className="text-sm font-medium text-gunmetal">{label}</span>
        <span className="text-xs text-gray-500">{sublabel}</span>
      </div>
    </div>
  );
}

export function DecisionQueueSummaryBar({
  summary,
  isLoading,
  onRefresh,
}: DecisionQueueSummaryBarProps) {
  const { requires_decision, being_handled, monitoring } = summary;

  // Format sublabels
  const decisionSublabel = requires_decision.total_at_risk > 0
    ? `${formatAmount(requires_decision.total_at_risk)} at risk`
    : 'No risk';

  const handlingSublabel = being_handled.has_executing
    ? `${being_handled.count} executing`
    : 'None executing';

  const monitoringSublabel = monitoring.total_upcoming > 0
    ? `${formatAmount(monitoring.total_upcoming)} upcoming`
    : 'No upcoming';

  return (
    <NeuroCard className="p-4">
      <div className="flex items-center justify-between flex-wrap gap-4">
        {/* Summary items */}
        <div className="flex items-center gap-8 flex-wrap">
          {/* Requires Decision */}
          <SummaryItem
            count={requires_decision.count}
            label="Require Decision"
            sublabel={decisionSublabel}
            badgeColor="bg-tomato/10 text-tomato"
          />

          {/* Divider */}
          <div className="hidden sm:block w-px h-10 bg-gray-200" />

          {/* Being Handled */}
          <SummaryItem
            count={being_handled.count}
            label="Being Handled"
            sublabel={handlingSublabel}
            badgeColor="bg-blue-500/10 text-blue-600"
          />

          {/* Divider */}
          <div className="hidden sm:block w-px h-10 bg-gray-200" />

          {/* Monitoring */}
          <SummaryItem
            count={monitoring.count}
            label="Monitoring"
            sublabel={monitoringSublabel}
            badgeColor="bg-lime/10 text-lime-700"
          />
        </div>

        {/* Refresh button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onRefresh}
          disabled={isLoading}
          className="text-gray-400 hover:text-gunmetal"
        >
          <RefreshCw
            className={cn(
              'w-4 h-4',
              isLoading && 'animate-spin'
            )}
          />
        </Button>
      </div>
    </NeuroCard>
  );
}
