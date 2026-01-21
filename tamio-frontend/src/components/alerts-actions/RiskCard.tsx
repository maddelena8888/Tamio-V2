/**
 * RiskCard Component - V4 Risk/Controls Architecture
 *
 * Displays a risk card with:
 * - Severity badge + due horizon
 * - Cash/buffer impact
 * - Primary driver
 * - "Review with Tammy" and "View details" CTAs
 * - Highlighting when linked control is selected
 */

import { cn } from '@/lib/utils';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import {
  AlertCircle,
  MessageSquare,
  ChevronRight,
  Clock,
  TrendingDown,
} from 'lucide-react';
import type { Risk } from '@/lib/api/alertsActions';
import { getSeverityStyles } from '@/lib/api/alertsActions';

interface RiskCardProps {
  risk: Risk;
  isHighlighted: boolean;
  isSelected: boolean;
  linkedControlCount: number;
  onReviewWithTammy: () => void;
  onViewDetails: () => void;
  onSelect: () => void;
}

export function RiskCard({
  risk,
  isHighlighted,
  isSelected,
  linkedControlCount,
  onReviewWithTammy,
  onViewDetails,
  onSelect,
}: RiskCardProps) {
  const severityStyles = getSeverityStyles(risk.severity);

  const formatAmount = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '--';
    const absValue = Math.abs(value);
    if (absValue >= 1000000) {
      return `$${(absValue / 1000000).toFixed(1)}M`;
    }
    if (absValue >= 1000) {
      return `$${(absValue / 1000).toFixed(0)}K`;
    }
    return `$${absValue.toLocaleString()}`;
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <NeuroCard
      onClick={onSelect}
      className={cn(
        'p-4 cursor-pointer transition-all duration-200',
        // Highlight when linked control selected
        isHighlighted && 'ring-2 ring-lime ring-offset-2',
        // Selected state
        isSelected && 'ring-2 ring-gunmetal/50 ring-offset-1',
        // Hover
        !isHighlighted && !isSelected && 'hover:shadow-lg'
      )}
    >
      {/* Header: Severity + Due Horizon */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'px-2.5 py-1 rounded-full text-xs font-semibold',
              severityStyles.bgClass,
              severityStyles.textClass
            )}
          >
            {risk.severity.charAt(0).toUpperCase() + risk.severity.slice(1)}
          </span>
          {risk.due_horizon_label && risk.due_horizon_label !== 'No deadline' && (
            <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 text-xs text-gray-600">
              <Clock className="w-3 h-3" />
              {risk.due_horizon_label}
            </span>
          )}
        </div>

        {linkedControlCount > 0 && (
          <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 text-xs font-medium">
            {linkedControlCount} control{linkedControlCount > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Title */}
      <h3 className="font-semibold text-sm leading-snug text-gunmetal mb-2 line-clamp-2">
        {risk.title}
      </h3>

      {/* Detected date + Impact */}
      <div className="flex items-center gap-4 text-xs text-gray-500 mb-3">
        <span>Detected {formatDate(risk.detected_at)}</span>

        {risk.cash_impact && (
          <>
            <span className="w-1 h-1 rounded-full bg-gray-300" />
            <span className={cn(
              'font-medium',
              risk.cash_impact < 0 ? 'text-tomato' : 'text-lime-600'
            )}>
              {formatAmount(risk.cash_impact)}
            </span>
          </>
        )}

        {risk.buffer_impact_percent && (
          <>
            <span className="w-1 h-1 rounded-full bg-gray-300" />
            <span className="flex items-center gap-1 text-amber-600">
              <TrendingDown className="w-3 h-3" />
              {risk.buffer_impact_percent}% of buffer
            </span>
          </>
        )}
      </div>

      {/* Primary Driver */}
      {risk.primary_driver && (
        <p className="text-xs text-gray-500 mb-4 line-clamp-1">
          <span className="text-gray-400">Likely cause:</span> {risk.primary_driver}
        </p>
      )}

      {/* CTAs */}
      <div className="flex gap-2 mt-auto">
        <Button
          onClick={(e) => {
            e.stopPropagation();
            onReviewWithTammy();
          }}
          className="flex-1 h-9 bg-lime hover:bg-lime/90 text-gunmetal text-xs font-medium"
        >
          <MessageSquare className="w-3.5 h-3.5 mr-1.5" />
          Review with Tammy
        </Button>

        <Button
          variant="outline"
          onClick={(e) => {
            e.stopPropagation();
            onViewDetails();
          }}
          className="h-9 px-3 border-gray-200 hover:bg-gray-50 text-xs font-medium"
        >
          Details
          <ChevronRight className="w-3.5 h-3.5 ml-1" />
        </Button>
      </div>
    </NeuroCard>
  );
}

// ============================================================================
// Empty State
// ============================================================================

export function EmptyRiskState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-12 h-12 rounded-full bg-lime/10 flex items-center justify-center mb-4">
        <AlertCircle className="w-6 h-6 text-lime-600" />
      </div>
      <h3 className="text-base font-semibold text-gunmetal mb-1">
        No active risks
      </h3>
      <p className="text-sm text-gray-500 max-w-sm">
        Your cash flow is looking healthy. Tamio will alert you when risks are
        detected.
      </p>
    </div>
  );
}
