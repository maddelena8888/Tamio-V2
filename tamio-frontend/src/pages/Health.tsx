import { useTAMIPageContext } from '@/contexts/TAMIContext';
import { Skeleton } from '@/components/ui/skeleton';
import { useHealthData } from '@/hooks/useHealthData';
import {
  HealthRingsSection,
  MonitorCardsSection,
  CriticalAlertsSection,
} from '@/components/health';

// ============================================================================
// Loading Skeleton
// ============================================================================

function HealthSkeleton() {
  return (
    <div className="px-6 max-w-[1200px] mx-auto h-[calc(100vh-180px)] overflow-hidden flex flex-col">
      {/* Rings skeleton */}
      <div className="flex justify-center gap-12 lg:gap-20 mb-4 flex-shrink-0">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex flex-col items-center gap-2">
            <Skeleton className="w-[260px] h-[260px] rounded-full" />
            <Skeleton className="w-24 h-4" />
            <Skeleton className="w-32 h-3" />
          </div>
        ))}
      </div>

      {/* Monitor cards skeleton */}
      <div className="grid grid-cols-2 gap-6 mb-4 flex-shrink-0">
        <Skeleton className="h-[90px] rounded-2xl" />
        <Skeleton className="h-[90px] rounded-2xl" />
      </div>

      {/* Alerts skeleton */}
      <Skeleton className="w-40 h-7 mb-3 flex-shrink-0" />
      <Skeleton className="flex-1 min-h-[100px] rounded-2xl" />
    </div>
  );
}

// ============================================================================
// Error State
// ============================================================================

function ErrorState({ message }: { message: string }) {
  return (
    <div className="px-6 max-w-[1200px] mx-auto h-[calc(100vh-180px)] overflow-hidden flex items-center justify-center">
      <div className="rounded-2xl p-8 bg-tomato/10 border border-tomato/20 text-center">
        <h2 className="text-xl font-bold text-tomato mb-2">
          Unable to Load Health Metrics
        </h2>
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function Health() {
  const { data, isLoading, error, refetch } = useHealthData({
    pollingInterval: 60000, // Refresh every 60 seconds
  });

  // Register page context for TAMI
  useTAMIPageContext({
    page: 'health',
    pageData: data ? {
      runway_weeks: data.runway.value,
      liquidity_ratio: data.liquidity.value,
      cash_velocity_days: data.cash_velocity.value,
      obligations_status: data.obligations_health.status,
      obligations_covered: data.obligations_health.covered_count,
      obligations_total: data.obligations_health.total_count,
      receivables_status: data.receivables_health.status,
      receivables_overdue: data.receivables_health.overdue_amount,
      critical_alerts_count: data.critical_alerts.length,
    } : undefined,
  });

  const handleAlertDismissed = () => {
    // Refetch data to update alerts count
    refetch();
  };

  // Loading state
  if (isLoading) {
    return <HealthSkeleton />;
  }

  // Error state
  if (error || !data) {
    return <ErrorState message={error || 'Failed to load health metrics'} />;
  }

  return (
    <div className="px-6 pt-4 max-w-[1200px] mx-auto h-[calc(100vh-180px)] overflow-hidden flex flex-col">
      {/* Health Rings Section */}
      <HealthRingsSection data={data} className="flex-shrink-0" />

      {/* Monitor Cards Section */}
      <MonitorCardsSection data={data} className="flex-shrink-0" />

      {/* Critical Alerts Section */}
      <CriticalAlertsSection
        alerts={data.critical_alerts}
        onDismissed={handleAlertDismissed}
        className="flex-1 min-h-0 overflow-hidden"
      />
    </div>
  );
}
