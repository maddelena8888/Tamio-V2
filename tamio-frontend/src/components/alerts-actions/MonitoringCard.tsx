/**
 * MonitoringCard Component
 *
 * Displays a compact card for items in the "Monitoring" section.
 * These are FYI items that don't require immediate action.
 *
 * Simplified layout:
 * - Title + FYI badge
 * - Due date + amount
 * - Brief status text
 */

import { Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DecisionItem } from '@/lib/api/alertsActions';
import { formatAmount } from '@/lib/utils/decisionQueue';

interface MonitoringCardProps {
  item: DecisionItem;
  onViewDetails?: (item: DecisionItem) => void;
}

export function MonitoringCard({ item, onViewDetails }: MonitoringCardProps) {
  const { alert, recommendation } = item;

  // Generate a contextual description based on available data
  const getDescription = (): string => {
    // Use recommendation's why_it_exists if available
    // But skip if it's just "Created in response to: [title]" which is not helpful
    if (recommendation?.why_it_exists &&
        !recommendation.why_it_exists.toLowerCase().startsWith('created in response to')) {
      return recommendation.why_it_exists;
    }

    // Use alert's primary_driver if available
    if (alert.primary_driver) {
      return alert.primary_driver;
    }

    // Use first context bullet as fallback
    if (alert.context_bullets?.length > 0) {
      return alert.context_bullets[0];
    }

    // Final fallback
    return 'Being monitored - no action required at this time.';
  };

  return (
    <div
      className={cn(
        'p-4 sm:p-5 bg-white',
        onViewDetails && 'cursor-pointer hover:bg-gray-50/50 transition-colors'
      )}
      onClick={() => onViewDetails?.(item)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header: Title + FYI badge */}
          <div className="flex items-start gap-2 mb-1">
            <h4 className="font-medium text-sm text-gunmetal flex-1 min-w-0">
              {alert.title}
            </h4>
            <span
              className={cn(
                'px-2 py-0.5 rounded text-[10px] font-medium uppercase flex-shrink-0',
                'bg-lime/10 text-lime-700 border border-lime/20'
              )}
            >
              FYI
            </span>
          </div>

          {/* Due date info */}
          {alert.due_horizon_label && alert.due_horizon_label !== 'No deadline' && (
            <p className="text-xs text-gray-500 flex items-center gap-1 mb-2">
              <Clock className="w-3 h-3" />
              {alert.due_horizon_label}
              {alert.deadline && (
                <span className="text-gray-400">
                  {' '}
                  &bull;{' '}
                  {new Date(alert.deadline).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
              )}
            </p>
          )}

          {/* Status message */}
          <p className="text-xs text-gray-500 line-clamp-2">{getDescription()}</p>
        </div>

        {/* Amount (right side) */}
        {alert.cash_impact && (
          <span className="text-sm font-medium text-gray-600 flex-shrink-0">
            {formatAmount(alert.cash_impact)}
          </span>
        )}
      </div>
    </div>
  );
}
