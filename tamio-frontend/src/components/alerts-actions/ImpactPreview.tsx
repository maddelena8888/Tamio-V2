/**
 * ImpactPreview Component
 *
 * A condensed version of the Alert Impact page for inline expansion within alert cards.
 * Shows the impact visualization chart and top 2 fix options.
 * Lazy-loads data only when expanded.
 */

import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import { ImpactVisualization, FixOptionCard } from '@/components/impact';
import { useImpactData } from '@/hooks/useImpactData';
import { approveControl, type Risk } from '@/lib/api/alertsActions';
import type { FixRecommendation } from '@/components/impact/types';

interface ImpactPreviewProps {
  alertId: string;
  alert: Risk;
  isExpanded: boolean;
}

export function ImpactPreview({ alertId, alert, isExpanded }: ImpactPreviewProps) {
  const navigate = useNavigate();

  const {
    forecast,
    isLoading,
    error,
    dangerZone,
    bufferAmount,
    alertWeek,
    fixes,
    refetch,
  } = useImpactData(alertId, isExpanded, { maxFixes: 2 });

  // Handle fix selection
  const handleSelectFix = useCallback(
    async (fix: FixRecommendation) => {
      switch (fix.action.type) {
        case 'approve_control': {
          try {
            await approveControl(fix.action.payload.controlId as string);
            toast.success('Fix approved successfully');
            // Refresh data
            await refetch();
          } catch (err) {
            console.error('Failed to approve control:', err);
            toast.error('Failed to approve fix');
          }
          break;
        }
        case 'run_scenario': {
          const params = new URLSearchParams();
          params.set('type', fix.action.payload.type as string);
          if (fix.action.payload.alertId) {
            params.set('alertId', fix.action.payload.alertId as string);
          }
          navigate(`/scenarios?${params.toString()}`);
          break;
        }
        case 'open_builder': {
          const params = new URLSearchParams();
          if (fix.action.payload.alertId) {
            params.set('alertId', fix.action.payload.alertId as string);
          }
          navigate(`/scenarios?${params.toString()}`);
          break;
        }
      }
    },
    [navigate, refetch]
  );

  const handleViewFullImpact = useCallback(() => {
    navigate(`/alerts/${alertId}/impact`);
  }, [navigate, alertId]);

  // Loading state
  if (isLoading) {
    return <ImpactPreviewSkeleton />;
  }

  // Error state
  if (error || !forecast) {
    return (
      <div className="p-6 text-center">
        <p className="text-sm text-muted-foreground mb-3">
          {error || 'Failed to load impact data'}
        </p>
        <Button variant="outline" size="sm" onClick={refetch}>
          Try Again
        </Button>
      </div>
    );
  }

  // Show only first 2 fixes for preview
  const previewFixes = fixes.slice(0, 2);

  return (
    <div className="p-4 pt-0 space-y-4">
      {/* Divider */}
      <div className="border-t border-gray-100" />

      {/* Chart - smaller height for preview */}
      <div className="rounded-xl overflow-hidden bg-white/30 backdrop-blur-sm">
        <div className="h-[220px]">
          <ImpactVisualization
            forecast={forecast}
            dangerZone={dangerZone}
            alertWeek={alertWeek}
            bufferAmount={bufferAmount}
            alertImpact={alert.cash_impact}
            impactWeek={alertWeek}
          />
        </div>
      </div>

      {/* Fix options - 2 columns for preview */}
      {previewFixes.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {previewFixes.map((fix, index) => (
            <FixOptionCard
              key={fix.id}
              number={(index + 1) as 1 | 2 | 3}
              fix={fix}
              onSelect={() => handleSelectFix(fix)}
            />
          ))}
        </div>
      )}

      {/* View Full Impact button */}
      <div className="pt-2">
        <Button
          onClick={handleViewFullImpact}
          variant="outline"
          className="w-full bg-white/50 hover:bg-white/70 border-gray-200"
        >
          <ExternalLink className="w-4 h-4 mr-2" />
          View Full Impact
        </Button>
      </div>
    </div>
  );
}

/**
 * Loading skeleton for the impact preview
 */
function ImpactPreviewSkeleton() {
  return (
    <div className="p-4 pt-0 space-y-4">
      {/* Divider */}
      <div className="border-t border-gray-100" />

      {/* Chart skeleton */}
      <div className="rounded-xl overflow-hidden bg-white/30 backdrop-blur-sm p-4">
        <div className="flex items-center justify-center h-[180px]">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>

      {/* Fix options skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {[1, 2].map((i) => (
          <div key={i} className="p-4 rounded-xl bg-white/30 backdrop-blur-sm">
            <Skeleton className="h-4 w-16 mx-auto mb-3" />
            <Skeleton className="h-5 w-32 mx-auto mb-2" />
            <Skeleton className="h-4 w-full mb-3" />
            <Skeleton className="h-9 w-full" />
          </div>
        ))}
      </div>

      {/* Button skeleton */}
      <Skeleton className="h-10 w-full" />
    </div>
  );
}
