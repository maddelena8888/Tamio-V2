import { useState } from 'react';
import { cn } from '@/lib/utils';
import { HealthRing, type RingMetric } from './HealthRing';
import { MetricExplanationDialog } from './MetricExplanationDialog';
import type { HealthMetricsResponse } from '@/lib/api/health';

// ============================================================================
// Types
// ============================================================================

export interface HealthRingsSectionProps {
  /** Health metrics data */
  data: HealthMetricsResponse;
  /** Additional class names */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

export function HealthRingsSection({
  data,
  className,
}: HealthRingsSectionProps) {
  const [selectedMetric, setSelectedMetric] = useState<RingMetric | null>(null);

  // Get the data for the currently selected metric
  const getSelectedData = () => {
    if (!selectedMetric) return null;
    switch (selectedMetric) {
      case 'runway':
        return data.runway;
      case 'liquidity':
        return data.liquidity;
      case 'cash_velocity':
        return data.cash_velocity;
      default:
        return null;
    }
  };

  const handleRingClick = (metric: RingMetric) => {
    setSelectedMetric(metric);
  };

  const handleDialogClose = () => {
    setSelectedMetric(null);
  };

  return (
    <section className={cn('-mt-4 mb-4', className)}>
      {/* Desktop: horizontal layout */}
      <div className="hidden md:flex justify-center items-start gap-10 lg:gap-16">
        <HealthRing
          metric="runway"
          data={data.runway}
          size="xl"
          onClick={() => handleRingClick('runway')}
        />
        <HealthRing
          metric="liquidity"
          data={data.liquidity}
          size="xl"
          onClick={() => handleRingClick('liquidity')}
        />
        <HealthRing
          metric="cash_velocity"
          data={data.cash_velocity}
          size="xl"
          onClick={() => handleRingClick('cash_velocity')}
        />
      </div>

      {/* Mobile: vertical layout */}
      <div className="flex md:hidden flex-col items-center gap-10">
        <HealthRing
          metric="runway"
          data={data.runway}
          size="md"
          onClick={() => handleRingClick('runway')}
        />
        <HealthRing
          metric="liquidity"
          data={data.liquidity}
          size="md"
          onClick={() => handleRingClick('liquidity')}
        />
        <HealthRing
          metric="cash_velocity"
          data={data.cash_velocity}
          size="md"
          onClick={() => handleRingClick('cash_velocity')}
        />
      </div>

      {/* Metric Explanation Dialog */}
      <MetricExplanationDialog
        metric={selectedMetric}
        data={getSelectedData()}
        onClose={handleDialogClose}
      />
    </section>
  );
}

export default HealthRingsSection;
