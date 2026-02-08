/**
 * ReconciliationTransactionTable Component
 *
 * Displays a table of payment transactions with reconciliation status,
 * AI confidence indicators, and inline action buttons.
 */

import { useState } from 'react';
import { Check, X, Pencil, Loader2, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { ReconciliationStatusBadge } from './ReconciliationStatusBadge';
import { AIConfidenceIndicator } from './AIConfidenceIndicator';
import { VarianceBadge } from './VarianceBadge';
import type { PaymentEvent, ReconciliationStatus, ObligationSchedule } from '@/lib/api/types';

interface EnhancedPaymentEvent extends PaymentEvent {
  reconciliation_status: ReconciliationStatus;
  ai_category?: string;
  ai_confidence?: number;
  matched_schedule?: ObligationSchedule;
  matched_obligation_name?: string;
}

interface ReconciliationTransactionTableProps {
  transactions: EnhancedPaymentEvent[];
  isLoading?: boolean;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  onApprove?: (payment: EnhancedPaymentEvent) => Promise<void>;
  onReject?: (payment: EnhancedPaymentEvent) => Promise<void>;
  onEdit?: (payment: EnhancedPaymentEvent) => void;
  onViewDetails?: (payment: EnhancedPaymentEvent) => void;
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

type SortKey = 'date' | 'amount' | 'status' | 'confidence';
type SortOrder = 'asc' | 'desc';

export function ReconciliationTransactionTable({
  transactions,
  isLoading = false,
  selectedIds = new Set(),
  onSelectionChange,
  onApprove,
  onReject,
  onEdit,
  onViewDetails,
  className,
}: ReconciliationTransactionTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };

  const sortedTransactions = [...transactions].sort((a, b) => {
    let comparison = 0;
    switch (sortKey) {
      case 'date':
        comparison = new Date(a.payment_date).getTime() - new Date(b.payment_date).getTime();
        break;
      case 'amount':
        comparison = parseFloat(a.amount) - parseFloat(b.amount);
        break;
      case 'status':
        const statusOrder = { reconciled: 0, ai_suggested: 1, pending: 2, unmatched: 3 };
        comparison = statusOrder[a.reconciliation_status] - statusOrder[b.reconciliation_status];
        break;
      case 'confidence':
        comparison = (a.ai_confidence || 0) - (b.ai_confidence || 0);
        break;
    }
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  const handleSelectAll = () => {
    if (!onSelectionChange) return;
    if (selectedIds.size === transactions.length) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(transactions.map((t) => t.id)));
    }
  };

  const handleSelectOne = (id: string) => {
    if (!onSelectionChange) return;
    const newSelection = new Set(selectedIds);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    onSelectionChange(newSelection);
  };

  const handleApprove = async (payment: EnhancedPaymentEvent) => {
    if (!onApprove) return;
    setLoadingIds((prev) => new Set(prev).add(payment.id));
    try {
      await onApprove(payment);
    } finally {
      setLoadingIds((prev) => {
        const next = new Set(prev);
        next.delete(payment.id);
        return next;
      });
    }
  };

  const handleReject = async (payment: EnhancedPaymentEvent) => {
    if (!onReject) return;
    setLoadingIds((prev) => new Set(prev).add(payment.id));
    try {
      await onReject(payment);
    } finally {
      setLoadingIds((prev) => {
        const next = new Set(prev);
        next.delete(payment.id);
        return next;
      });
    }
  };

  const SortIcon = ({ column }: { column: SortKey }) => {
    if (sortKey !== column) {
      return <ChevronDown className="w-3 h-3 text-gray-400" />;
    }
    return sortOrder === 'asc' ? (
      <ChevronUp className="w-3 h-3" />
    ) : (
      <ChevronDown className="w-3 h-3" />
    );
  };

  if (isLoading) {
    return (
      <div className={cn('rounded-xl border border-white/50 bg-white/40 backdrop-blur-sm', className)}>
        <div className="p-8 text-center">
          <Loader2 className="w-6 h-6 animate-spin mx-auto text-mimi-pink" />
          <p className="mt-2 text-sm text-gray-500">Loading transactions...</p>
        </div>
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <div className={cn('rounded-xl border border-white/50 bg-white/40 backdrop-blur-sm', className)}>
        <div className="p-8 text-center">
          <p className="text-sm text-gray-500">No transactions found.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('rounded-xl border border-white/50 bg-white/40 backdrop-blur-sm overflow-hidden', className)}>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50/50">
              {onSelectionChange && (
                <th className="w-12 py-3 px-4">
                  <Checkbox
                    checked={selectedIds.size === transactions.length && transactions.length > 0}
                    onCheckedChange={handleSelectAll}
                  />
                </th>
              )}
              <th
                className="text-left py-3 px-4 font-semibold text-sm text-gray-600 cursor-pointer hover:text-gray-900"
                onClick={() => handleSort('date')}
              >
                <div className="flex items-center gap-1">
                  Date
                  <SortIcon column="date" />
                </div>
              </th>
              <th
                className="text-right py-3 px-4 font-semibold text-sm text-gray-600 cursor-pointer hover:text-gray-900"
                onClick={() => handleSort('amount')}
              >
                <div className="flex items-center justify-end gap-1">
                  Amount
                  <SortIcon column="amount" />
                </div>
              </th>
              <th className="text-left py-3 px-4 font-semibold text-sm text-gray-600">
                Description
              </th>
              <th className="text-left py-3 px-4 font-semibold text-sm text-gray-600">
                AI Category
              </th>
              <th className="text-left py-3 px-4 font-semibold text-sm text-gray-600">
                Matched To
              </th>
              <th
                className="text-center py-3 px-4 font-semibold text-sm text-gray-600 cursor-pointer hover:text-gray-900"
                onClick={() => handleSort('confidence')}
              >
                <div className="flex items-center justify-center gap-1">
                  Confidence
                  <SortIcon column="confidence" />
                </div>
              </th>
              <th
                className="text-center py-3 px-4 font-semibold text-sm text-gray-600 cursor-pointer hover:text-gray-900"
                onClick={() => handleSort('status')}
              >
                <div className="flex items-center justify-center gap-1">
                  Status
                  <SortIcon column="status" />
                </div>
              </th>
              <th className="text-center py-3 px-4 font-semibold text-sm text-gray-600">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedTransactions.map((payment) => {
              const isLoading = loadingIds.has(payment.id);
              const showActions =
                payment.reconciliation_status === 'ai_suggested' ||
                payment.reconciliation_status === 'pending';

              return (
                <tr
                  key={payment.id}
                  className={cn(
                    'border-b border-gray-100 hover:bg-white/60 transition-colors',
                    selectedIds.has(payment.id) && 'bg-mimi-pink/5'
                  )}
                >
                  {onSelectionChange && (
                    <td className="py-3 px-4">
                      <Checkbox
                        checked={selectedIds.has(payment.id)}
                        onCheckedChange={() => handleSelectOne(payment.id)}
                      />
                    </td>
                  )}
                  <td className="py-3 px-4 text-sm text-gray-700">
                    {formatDate(payment.payment_date)}
                  </td>
                  <td className="py-3 px-4 text-sm font-medium text-right">
                    <span className={payment.source === 'bank_feed' ? 'text-lime-dark' : ''}>
                      {formatCurrency(payment.amount, payment.currency)}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">
                        {payment.vendor_name || 'Unknown'}
                      </span>
                      {payment.reference && (
                        <span className="text-xs text-gray-400">
                          #{payment.reference}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-500 capitalize">
                      {payment.source.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {payment.ai_category ? (
                      <Badge variant="outline" className="text-xs capitalize">
                        {payment.ai_category}
                      </Badge>
                    ) : (
                      <span className="text-xs text-gray-400">-</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    {payment.matched_obligation_name ? (
                      <div>
                        <span className="text-sm font-medium text-gray-900">
                          {payment.matched_obligation_name}
                        </span>
                        {payment.matched_schedule && (
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-gray-500">
                              Due: {formatDate(payment.matched_schedule.due_date)}
                            </span>
                            <VarianceBadge
                              actual={payment.amount}
                              expected={payment.matched_schedule.estimated_amount}
                              currency={payment.currency}
                            />
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">No match</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-center">
                    {payment.ai_confidence !== undefined ? (
                      <AIConfidenceIndicator confidence={payment.ai_confidence} size="sm" />
                    ) : (
                      <span className="text-xs text-gray-400">-</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <ReconciliationStatusBadge status={payment.reconciliation_status} />
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center justify-center gap-1">
                      {showActions && onApprove && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleApprove(payment)}
                          disabled={isLoading}
                          className="h-7 w-7 p-0 text-lime-dark hover:bg-lime/20"
                          title="Approve match"
                        >
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Check className="w-4 h-4" />
                          )}
                        </Button>
                      )}
                      {showActions && onEdit && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => onEdit(payment)}
                          disabled={isLoading}
                          className="h-7 w-7 p-0 text-gray-500 hover:bg-gray-100"
                          title="Edit match"
                        >
                          <Pencil className="w-4 h-4" />
                        </Button>
                      )}
                      {showActions && onReject && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleReject(payment)}
                          disabled={isLoading}
                          className="h-7 w-7 p-0 text-gray-400 hover:text-tomato hover:bg-tomato/10"
                          title="Reject match"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      )}
                      {onViewDetails && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => onViewDetails(payment)}
                          className="h-7 w-7 p-0 text-gray-400 hover:bg-gray-100"
                          title="View details"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ReconciliationTransactionTable;
