/**
 * Bank Accounts Overview Widget
 *
 * Shows all connected bank accounts with balances and last sync time.
 * Trust in data freshness.
 */

import { Link } from 'react-router-dom';
import { Building2, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import { useWidgetData } from '@/hooks/useDashboardData';
import { cn } from '@/lib/utils';
import { WidgetSkeleton } from './WidgetSkeleton';
import { WidgetEmptyState } from './WidgetEmptyState';
import type { WidgetProps } from './types';
import type { CashAccount } from '@/lib/api/types';

export function BankAccountsOverviewWidget({ className }: WidgetProps) {
  const { cashPosition, isLoading } = useWidgetData();

  if (isLoading) {
    return <WidgetSkeleton className={className} />;
  }

  if (!cashPosition || cashPosition.accounts.length === 0) {
    return (
      <WidgetEmptyState
        message="Connect a bank account to see your balances"
        actionLabel="Connect account"
        actionHref="/settings/integrations"
        icon={<Building2 className="w-8 h-8" />}
        className={className}
      />
    );
  }

  const { accounts, total_starting_cash } = cashPosition;
  const totalFormatted = formatCurrency(parseFloat(total_starting_cash));

  // Mock sync status (would come from API in real implementation)
  const syncStatus = 'synced' as const; // 'synced' | 'syncing' | 'error'

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Accounts
          </span>
        </div>
        <SyncStatus status={syncStatus} />
      </div>

      {/* Account List */}
      <div className="flex-1 space-y-2 overflow-hidden">
        {accounts.slice(0, 3).map((account: CashAccount, index: number) => (
          <div
            key={index}
            className="flex items-center justify-between p-2 rounded-lg bg-white/30"
          >
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-full bg-gunmetal/10 flex items-center justify-center flex-shrink-0">
                <Building2 className="w-3 h-3 text-gunmetal" />
              </div>
              <span className="text-sm font-medium text-gunmetal truncate">
                {account.account_name}
              </span>
            </div>
            <span className="text-sm font-semibold text-gunmetal ml-2">
              {formatCurrency(parseFloat(account.balance))}
            </span>
          </div>
        ))}
        {accounts.length > 3 && (
          <div className="text-xs text-muted-foreground text-center py-1">
            +{accounts.length - 3} more account{accounts.length - 3 !== 1 ? 's' : ''}
          </div>
        )}
      </div>

      {/* Total */}
      <div className="pt-3 border-t border-white/20">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Total</span>
          <span className="text-lg font-bold text-gunmetal">{totalFormatted}</span>
        </div>
      </div>

      {/* Action Link */}
      <div className="flex justify-center pt-2">
        <Link to="/settings/integrations" className="text-xs text-gunmetal hover:underline">
          Manage accounts &rarr;
        </Link>
      </div>
    </div>
  );
}

// ============================================================================
// Sync Status Component
// ============================================================================

interface SyncStatusProps {
  status: 'synced' | 'syncing' | 'error';
}

function SyncStatus({ status }: SyncStatusProps) {
  if (status === 'syncing') {
    return (
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <RefreshCw className="w-3 h-3 animate-spin" />
        <span>Syncing...</span>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex items-center gap-1 text-xs text-tomato">
        <AlertCircle className="w-3 h-3" />
        <span>Sync error</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground">
      <CheckCircle className="w-3 h-3 text-lime-600" />
      <span>Synced</span>
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
