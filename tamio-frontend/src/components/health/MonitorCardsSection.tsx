import { useState } from 'react';
import { cn } from '@/lib/utils';
import { ObligationsCard } from './ObligationsCard';
import { ReceivablesCard } from './ReceivablesCard';
import { MonitorDetailDialog, type MonitorMetric } from './MonitorDetailDialog';
import type { HealthMetricsResponse } from '@/lib/api/health';

// ============================================================================
// Types
// ============================================================================

export interface MonitorCardsSectionProps {
  /** Health metrics data */
  data: HealthMetricsResponse;
  /** Additional class names */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

export function MonitorCardsSection({ data, className }: MonitorCardsSectionProps) {
  const [selectedMetric, setSelectedMetric] = useState<MonitorMetric | null>(null);

  const handleObligationsClick = () => {
    setSelectedMetric('obligations');
  };

  const handleReceivablesClick = () => {
    setSelectedMetric('receivables');
  };

  const handleDialogClose = () => {
    setSelectedMetric(null);
  };

  return (
    <section className={cn('mt-6 mb-4', className)}>
      {/* Desktop: side-by-side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ObligationsCard data={data.obligations_health} onClick={handleObligationsClick} />
        <ReceivablesCard data={data.receivables_health} onClick={handleReceivablesClick} />
      </div>

      <MonitorDetailDialog
        metric={selectedMetric}
        obligationsData={data.obligations_health}
        receivablesData={data.receivables_health}
        onClose={handleDialogClose}
      />
    </section>
  );
}

export default MonitorCardsSection;
