/**
 * Empty Dashboard - Shown when no cards are on the dashboard
 */

import { LayoutGrid, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useDashboard } from '@/contexts/DashboardContext';
import { cn } from '@/lib/utils';

interface EmptyDashboardProps {
  className?: string;
  onAddWidget?: () => void;
}

export function EmptyDashboard({ className, onAddWidget }: EmptyDashboardProps) {
  const { resetToPreset } = useDashboard();

  const handleStartWithLeader = () => {
    resetToPreset('leader');
  };

  const handleStartWithFinance = () => {
    resetToPreset('finance_manager');
  };

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 px-6 text-center',
        'rounded-2xl border-2 border-dashed border-gray-200 bg-white/20',
        className
      )}
    >
      {/* Icon */}
      <div className="w-16 h-16 rounded-full bg-gunmetal/5 flex items-center justify-center mb-4">
        <LayoutGrid className="w-8 h-8 text-gunmetal/40" />
      </div>

      {/* Message */}
      <h3 className="text-lg font-semibold text-gunmetal mb-2">
        Your dashboard is empty
      </h3>
      <p className="text-sm text-muted-foreground mb-6 max-w-sm">
        Add cards to see your financial health at a glance. Start with a preset view
        or build your own.
      </p>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3">
        <Button onClick={handleStartWithLeader} variant="default">
          Start with Leader View
        </Button>
        <Button onClick={handleStartWithFinance} variant="outline">
          Finance Manager View
        </Button>
      </div>

      {/* Or add custom */}
      {onAddWidget && (
        <div className="mt-6 pt-6 border-t border-gray-200 w-full max-w-xs">
          <button
            onClick={onAddWidget}
            className="flex items-center justify-center gap-2 text-sm text-gunmetal hover:text-gunmetal/80 transition-colors w-full"
          >
            <Plus className="w-4 h-4" />
            Or add cards individually
          </button>
        </div>
      )}
    </div>
  );
}
