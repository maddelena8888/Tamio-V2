/**
 * ReconciliationSuggestionCard Component
 *
 * Displays an AI reconciliation suggestion with approve/edit/reject actions.
 * Used in the Reconciliation Queue tab of the Ledger page.
 */

import { useState } from 'react';
import { Check, Pencil, X, Sparkles, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { AIConfidenceIndicator } from './AIConfidenceIndicator';
import { VarianceBadge } from './VarianceBadge';
import type { ReconciliationSuggestion } from '@/lib/api/types';

interface ReconciliationSuggestionCardProps {
  suggestion: ReconciliationSuggestion;
  onApprove: (suggestion: ReconciliationSuggestion) => Promise<void>;
  onEdit: (suggestion: ReconciliationSuggestion) => void;
  onReject: (suggestion: ReconciliationSuggestion) => Promise<void>;
  className?: string;
}

function formatCurrency(value: number | string, currency: string = 'USD'): string {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function ReconciliationSuggestionCard({
  suggestion,
  onApprove,
  onEdit,
  onReject,
  className,
}: ReconciliationSuggestionCardProps) {
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      await onApprove(suggestion);
    } finally {
      setIsApproving(false);
    }
  };

  const handleReject = async () => {
    setIsRejecting(true);
    try {
      await onReject(suggestion);
    } finally {
      setIsRejecting(false);
    }
  };

  const { payment, suggested_schedule, suggested_obligation } = suggestion;

  return (
    <div
      className={cn(
        'relative rounded-xl',
        'backdrop-blur-sm',
        'border border-white/50',
        'shadow-lg shadow-black/5',
        'bg-mimi-pink/5',
        className
      )}
    >
      <div className="p-4 sm:p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-base font-bold text-gunmetal">
            {payment.vendor_name || 'Unknown Transaction'}
          </h3>
          <div className="flex items-center gap-2">
            {/* Amount pill */}
            <span className="px-2.5 py-1 rounded-full text-sm font-semibold bg-gray-100">
              {formatCurrency(payment.amount, payment.currency)}
            </span>
            {/* AI confidence */}
            <AIConfidenceIndicator confidence={suggestion.confidence} size="md" />
            {/* Dismiss button */}
            <button
              onClick={handleReject}
              disabled={isRejecting}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-50"
              title="Reject suggestion"
            >
              {isRejecting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <X className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* AI Insight */}
        <p className="text-sm text-gray-600 mb-4">
          <Sparkles className="w-4 h-4 inline mr-1 text-mimi-pink" />
          {suggestion.reasoning}
        </p>

        {/* Suggested Match */}
        <div className="bg-white/60 rounded-lg p-4 border border-gray-100 mb-4">
          <h4 className="text-sm font-semibold text-gunmetal mb-2">
            Suggested Match
          </h4>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gunmetal">
                {suggested_obligation.vendor_name || suggested_obligation.category}
              </p>
              <p className="text-xs text-gray-500">
                {formatDate(suggested_schedule.due_date)} | Expected: {formatCurrency(suggested_schedule.estimated_amount, payment.currency)}
              </p>
            </div>
            {/* Variance indicator */}
            {suggestion.variance_amount !== null && (
              <VarianceBadge
                actual={payment.amount}
                expected={suggested_schedule.estimated_amount}
                currency={payment.currency}
              />
            )}
          </div>
        </div>

        {/* Transaction Details */}
        <div className="text-xs text-gray-500 mb-4 space-y-1">
          <p>Payment Date: {formatDate(payment.payment_date)}</p>
          {payment.reference && <p>Reference: {payment.reference}</p>}
          <p>Source: {payment.source.replace('_', ' ')}</p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <Button
            onClick={handleApprove}
            disabled={isApproving || isRejecting}
            className="bg-lime text-gunmetal hover:bg-lime/90"
          >
            {isApproving ? (
              <Loader2 className="w-4 h-4 mr-1 animate-spin" />
            ) : (
              <Check className="w-4 h-4 mr-1" />
            )}
            Accept Match
          </Button>
          <Button
            variant="outline"
            onClick={() => onEdit(suggestion)}
            disabled={isApproving || isRejecting}
          >
            <Pencil className="w-4 h-4 mr-1" />
            Edit Match
          </Button>
          <Button
            variant="ghost"
            onClick={handleReject}
            disabled={isApproving || isRejecting}
            className="text-gray-500"
          >
            Reject
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ReconciliationSuggestionCard;
