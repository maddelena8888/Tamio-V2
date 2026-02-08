import { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import { AlertCard } from '../cards/AlertCard';
import { useNotificationCentre } from '../NotificationCentreContext';
import { getRisks, dismissRisk, type Risk, type RiskSeverity } from '@/lib/api/alertsActions';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const severityOrder: Record<RiskSeverity, number> = {
  urgent: 0,
  high: 1,
  normal: 2,
};

const severityLabels: Record<RiskSeverity, { label: string; bgClass: string; textClass: string }> = {
  urgent: { label: 'Urgent', bgClass: 'bg-tomato/5', textClass: 'text-tomato' },
  high: { label: 'High Priority', bgClass: 'bg-amber-500/5', textClass: 'text-amber-600' },
  normal: { label: 'Normal', bgClass: 'bg-lime/5', textClass: 'text-lime-700' },
};

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-full bg-lime/10 flex items-center justify-center mb-3">
        <CheckCircle2 className="w-6 h-6 text-lime-600" />
      </div>
      <h3 className="text-sm font-semibold text-gunmetal mb-1">All clear!</h3>
      <p className="text-xs text-muted-foreground max-w-[250px]">
        No active alerts at the moment. We'll notify you when something needs your attention.
      </p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="p-3 rounded-xl border border-gray-100">
          <div className="flex gap-3">
            <Skeleton className="w-8 h-8 rounded-lg" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

const INITIAL_VISIBLE = 3;

export function AlertsTab() {
  const { setUnreadCounts, unreadCounts } = useNotificationCentre();
  const [risks, setRisks] = useState<Risk[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    async function fetchRisks() {
      try {
        const response = await getRisks({ status: 'active' });
        setRisks(response.risks);

        // Update unread count (all active alerts are considered unread initially)
        const unreadCount = response.risks.filter(r => !readIds.has(r.id)).length;
        setUnreadCounts({
          ...unreadCounts,
          alerts: unreadCount,
        });
      } catch (error) {
        console.error('Failed to fetch risks:', error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchRisks();
  }, []);

  const handleDismiss = async (id: string) => {
    try {
      await dismissRisk(id);
      setRisks((prev) => prev.filter((r) => r.id !== id));

      // Update unread count
      if (!readIds.has(id)) {
        setUnreadCounts({
          ...unreadCounts,
          alerts: Math.max(0, unreadCounts.alerts - 1),
        });
      }
    } catch (error) {
      console.error('Failed to dismiss risk:', error);
    }
  };

  const handleMarkRead = (id: string) => {
    setReadIds((prev) => new Set([...prev, id]));
    setUnreadCounts({
      ...unreadCounts,
      alerts: Math.max(0, unreadCounts.alerts - 1),
    });
  };

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  if (risks.length === 0) {
    return <EmptyState />;
  }

  // Sort all risks by severity, then by cash impact
  const sortedRisks = [...risks].sort((a, b) => {
    const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
    if (severityDiff !== 0) return severityDiff;
    return Math.abs(b.cash_impact || 0) - Math.abs(a.cash_impact || 0);
  });

  const visibleRisks = isExpanded ? sortedRisks : sortedRisks.slice(0, INITIAL_VISIBLE);
  const hiddenCount = sortedRisks.length - INITIAL_VISIBLE;

  return (
    <div className="space-y-3">
      {/* Alert Cards */}
      <div className="space-y-2">
        {visibleRisks.map((risk) => (
          <AlertCard
            key={risk.id}
            risk={risk}
            onDismiss={handleDismiss}
            onMarkRead={handleMarkRead}
            isRead={readIds.has(risk.id)}
          />
        ))}
      </div>

      {/* Expand/Collapse Button */}
      {hiddenCount > 0 && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-center gap-2 py-2.5 text-sm text-muted-foreground hover:text-gunmetal hover:bg-gray-50 rounded-lg transition-colors"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="w-4 h-4" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="w-4 h-4" />
              Show {hiddenCount} more alert{hiddenCount !== 1 ? 's' : ''}
            </>
          )}
        </button>
      )}
    </div>
  );
}
