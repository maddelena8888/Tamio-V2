/**
 * AlertImpactModal Component
 *
 * Modal popup showing alert impact details including:
 * - Title and impact sentence
 * - Forecast visualization with impact overlay
 * - Suggested actions/fixes
 */

import { useNavigate } from 'react-router-dom';
import { X, TrendingDown, Zap, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ImpactVisualization } from '@/components/impact/ImpactVisualization';
import { useImpactData } from '@/hooks/useImpactData';
import { getSeverityStyles } from '@/lib/api/alertsActions';
import type { FixRecommendation } from '@/components/impact/types';
import type { AlertPanelItem } from './types';

/**
 * Fix card for modal with context
 */
function ModalFixCard({
  fix,
  onSelect
}: {
  fix: FixRecommendation;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'flex flex-col p-4 rounded-xl',
        'bg-white/60 backdrop-blur-sm border border-white/40',
        'hover:bg-white/80 hover:shadow-md transition-all',
        'text-left w-full group'
      )}
    >
      <h4 className="font-semibold text-gunmetal text-sm mb-1">
        {fix.title}
      </h4>
      <p className="text-xs text-gray-500 mb-3 line-clamp-2">
        {fix.description}
      </p>
      <div className="flex items-center justify-between mt-auto">
        {fix.buffer_improvement && (
          <span className="text-xs font-medium text-lime-700 bg-lime/20 px-2 py-0.5 rounded">
            {fix.buffer_improvement}
          </span>
        )}
        <span className="text-xs text-gunmetal font-medium group-hover:underline ml-auto flex items-center gap-1">
          Apply <ChevronRight className="w-3 h-3" />
        </span>
      </div>
    </button>
  );
}

interface AlertImpactModalProps {
  item: AlertPanelItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Loading skeleton for the modal content
 */
function ModalSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Title skeleton */}
      <div className="h-6 bg-gray-200 rounded w-3/4" />

      {/* Impact sentence skeleton */}
      <div className="h-4 bg-gray-200 rounded w-full" />

      {/* Chart skeleton */}
      <div className="h-[280px] bg-gray-100 rounded-2xl" />

      {/* Actions skeleton */}
      <div className="grid grid-cols-2 gap-4">
        <div className="h-32 bg-gray-100 rounded-xl" />
        <div className="h-32 bg-gray-100 rounded-xl" />
      </div>
    </div>
  );
}

export function AlertImpactModal({
  item,
  open,
  onOpenChange,
}: AlertImpactModalProps) {
  const navigate = useNavigate();

  // Use the shared impact data hook
  const {
    alert: fullAlert,
    forecast,
    isLoading,
    error,
    dangerZone,
    bufferAmount,
    alertWeek,
    fixes,
  } = useImpactData(item?.alert.id || '', open, { maxFixes: 2 });

  // Use data from the item prop for initial display, fullAlert for complete data
  const alert = item?.alert;
  const styles = alert ? getSeverityStyles(alert.severity) : null;

  // Handle fix selection
  const handleFixSelect = (fix: typeof fixes[0]) => {
    onOpenChange(false);

    switch (fix.action.type) {
      case 'approve_control':
        // Navigate to health page with control action
        navigate(`/health?alert=${alert?.id}&action=true`);
        break;
      case 'run_scenario':
        // Navigate to scenarios with the scenario type
        const payload = fix.action.payload as { type: string; alertId: string };
        navigate(`/scenarios?type=${payload.type}&alertId=${payload.alertId}`);
        break;
      case 'open_builder':
        // Navigate to scenario builder
        navigate(`/scenarios?alertId=${alert?.id}`);
        break;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          'sm:max-w-[900px] max-h-[95vh]',
          'bg-white/95 backdrop-blur-xl',
          'border border-white/60',
          'shadow-[0_8px_32px_rgba(0,0,0,0.12)]'
        )}
        showCloseButton={false}
      >
        {/* Custom close button */}
        <button
          onClick={() => onOpenChange(false)}
          className={cn(
            'absolute top-4 right-4 z-10',
            'w-8 h-8 rounded-full bg-white/60 backdrop-blur-sm',
            'flex items-center justify-center',
            'hover:bg-white transition-colors',
            'border border-white/40'
          )}
        >
          <X className="w-4 h-4 text-gray-600" />
        </button>

        {!alert ? (
          <div className="py-8 text-center text-gray-500">
            No alert selected
          </div>
        ) : isLoading ? (
          <ModalSkeleton />
        ) : error ? (
          <div className="py-8 text-center text-gray-500">
            <p>Failed to load impact data</p>
            <Button variant="ghost" size="sm" className="mt-2" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Header with severity badge */}
            <DialogHeader className="pr-8">
              <div className="flex items-center gap-2 mb-2">
                {styles && (
                  <span className={cn(
                    'px-2.5 py-1 rounded-full text-xs font-semibold',
                    styles.bgClass, styles.textClass
                  )}>
                    {alert.severity === 'urgent' ? 'Urgent' : alert.severity === 'high' ? 'High' : 'FYI'}
                  </span>
                )}
                {alert.due_horizon_label && (
                  <span className="text-xs text-gray-500">
                    {alert.due_horizon_label}
                  </span>
                )}
              </div>
              <DialogTitle className="text-xl font-bold text-gunmetal leading-tight">
                {alert.title}
              </DialogTitle>
            </DialogHeader>

            {/* Impact statement */}
            {(fullAlert?.impact_statement || fullAlert?.primary_driver) && (
              <div className={cn(
                'p-3 rounded-xl',
                'bg-gradient-to-r from-tomato/5 to-transparent',
                'border-l-4 border-tomato'
              )}>
                <div className="flex items-start gap-2">
                  <TrendingDown className="w-4 h-4 text-tomato flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-gunmetal leading-snug">
                    {fullAlert.impact_statement || fullAlert.primary_driver}
                  </p>
                </div>
              </div>
            )}

            {/* Forecast visualization */}
            {forecast && (
              <div>
                <ImpactVisualization
                  forecast={forecast}
                  dangerZone={dangerZone}
                  alertWeek={alertWeek}
                  bufferAmount={bufferAmount}
                  alertImpact={alert.cash_impact}
                  compact
                />
              </div>
            )}

            {/* Suggested actions */}
            {fixes.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-lime" />
                  <h4 className="font-semibold text-gunmetal text-sm">Suggested Actions</h4>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {fixes.map((fix) => (
                    <ModalFixCard
                      key={fix.id}
                      fix={fix}
                      onSelect={() => handleFixSelect(fix)}
                    />
                  ))}
                </div>
              </div>
            )}

          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
