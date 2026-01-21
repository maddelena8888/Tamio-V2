/**
 * BeingHandledCard Component
 *
 * Displays a card for items in the "Being Handled" section.
 * Shows active controls that are currently executing.
 *
 * Simplified layout:
 * - Alert title
 * - Active control name + status
 * - View Details button
 */

import { Shield, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import type { DecisionItem } from '@/lib/api/alertsActions';
import { formatAmount } from '@/lib/utils/decisionQueue';

interface BeingHandledCardProps {
  item: DecisionItem;
  onViewDetails: (item: DecisionItem) => void;
}

export function BeingHandledCard({ item, onViewDetails }: BeingHandledCardProps) {
  const { alert, activeControls } = item;
  const primaryControl = activeControls[0];

  // Generate a contextual description based on available data
  const getDescription = (): string => {
    // Use the control's why_it_exists if available
    // But skip if it's just "Created in response to: [title]" which is not helpful
    if (primaryControl?.why_it_exists &&
        !primaryControl.why_it_exists.toLowerCase().startsWith('created in response to')) {
      return primaryControl.why_it_exists;
    }

    // Use alert's primary_driver as fallback
    if (alert.primary_driver) {
      return alert.primary_driver;
    }

    // Use first context bullet if available
    if (alert.context_bullets?.length > 0) {
      return alert.context_bullets[0];
    }

    // Final fallback
    return 'Action in progress to address this alert';
  };

  return (
    <div className="p-4 sm:p-5 bg-white">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Alert title */}
          <h4 className="font-semibold text-sm text-gunmetal mb-1 truncate">
            {alert.title}
          </h4>

          {/* Contextual description */}
          <p className="text-xs text-gray-500 mb-2 line-clamp-2">
            {getDescription()}
          </p>

          {/* Active control info */}
          {primaryControl && (
            <div className="flex items-center gap-2 text-xs text-gray-600">
              <Shield className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
              <span className="truncate">{primaryControl.name}</span>
              <span
                className={cn(
                  'px-2 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0',
                  'bg-blue-50 text-blue-600'
                )}
              >
                In progress
              </span>
            </div>
          )}

          {/* Additional controls count */}
          {activeControls.length > 1 && (
            <p className="text-xs text-gray-400 mt-1">
              +{activeControls.length - 1} more control{activeControls.length > 2 ? 's' : ''}
            </p>
          )}
        </div>

        {/* Right side: Amount + View button */}
        <div className="flex flex-col items-end gap-2">
          {alert.cash_impact && (
            <span className="text-sm font-medium text-gray-600">
              {formatAmount(alert.cash_impact)}
            </span>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => onViewDetails(item)}
            className="text-xs text-gray-500 hover:text-gunmetal h-7 px-2"
          >
            View Details
            <ChevronRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  );
}
