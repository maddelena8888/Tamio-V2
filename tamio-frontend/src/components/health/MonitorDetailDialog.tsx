import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle, Check, Clock, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getSeverityStyles, type Risk } from '@/lib/api/alertsActions';
import type { ObligationsHealthData, ReceivablesHealthData } from '@/lib/api/health';
import { useMonitorAlerts, type MonitorCategory } from '@/hooks/useMonitorAlerts';

// ============================================================================
// Types
// ============================================================================

export type MonitorMetric = 'obligations' | 'receivables';

export interface MonitorDetailDialogProps {
  /** Which metric to show (null = dialog closed) */
  metric: MonitorMetric | null;
  /** Obligations health data (when metric is 'obligations') */
  obligationsData?: ObligationsHealthData;
  /** Receivables health data (when metric is 'receivables') */
  receivablesData?: ReceivablesHealthData;
  /** Called when dialog should close */
  onClose: () => void;
}

// ============================================================================
// Metric Content Configuration
// ============================================================================

interface MetricContent {
  title: string;
  question: string;
  whatItMeasures: string;
  thresholds: {
    good: { label: string; description: string };
    warning: { label: string; description: string };
    critical: { label: string; description: string };
  };
}

const METRIC_CONTENT: Record<MonitorMetric, MetricContent> = {
  obligations: {
    title: 'Obligations',
    question: 'Can you meet your upcoming payments?',
    whatItMeasures:
      'Compares your available cash against scheduled outgoing payments over the next 30 days, including vendor bills, payroll, subscriptions, and tax obligations.',
    thresholds: {
      good: { label: 'COVERED', description: 'All obligations can be paid with current cash' },
      warning: { label: 'TIGHT', description: 'Some obligations may require careful timing' },
      critical: { label: 'AT RISK', description: 'Insufficient funds for upcoming obligations' },
    },
  },
  receivables: {
    title: 'Receivables',
    question: 'Is money owed to you coming in on time?',
    whatItMeasures:
      'Tracks overdue amounts, invoice aging, and collection velocity across your client base to monitor the health of your accounts receivable.',
    thresholds: {
      good: { label: 'HEALTHY', description: 'Most invoices paid on time, low overdue balance' },
      warning: { label: 'WATCH', description: 'Growing overdue balance or aging invoices' },
      critical: { label: 'URGENT', description: 'Significant overdue amounts affecting cash flow' },
    },
  },
};

// ============================================================================
// Sub-Components
// ============================================================================

function AlertCardCompact({ alert, onClick }: { alert: Risk; onClick: () => void }) {
  const styles = getSeverityStyles(alert.severity);

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-4 rounded-lg border transition-colors',
        'hover:bg-gray-50',
        styles.borderClass
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={cn(
                'px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase',
                styles.bgClass,
                styles.textClass
              )}
            >
              {alert.severity}
            </span>
            {alert.due_horizon_label && alert.due_horizon_label !== 'No deadline' && (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Clock className="w-3 h-3" />
                {alert.due_horizon_label}
              </span>
            )}
          </div>
          <h4 className="text-sm font-medium text-gunmetal truncate">{alert.title}</h4>
          {alert.impact_statement && (
            <p className="text-xs text-gray-500 mt-1 line-clamp-2">{alert.impact_statement}</p>
          )}
        </div>
        <ArrowRight className="w-4 h-4 text-gray-400 flex-shrink-0 mt-1" />
      </div>
    </button>
  );
}

function AlertsLoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-20 rounded-lg" />
      ))}
    </div>
  );
}

function NoAlertsState({ category }: { category: MonitorCategory }) {
  return (
    <div className="text-center py-8">
      <Check className="w-10 h-10 text-lime mx-auto mb-3" />
      <p className="text-sm font-medium text-gunmetal">All Clear</p>
      <p className="text-xs text-gray-500 mt-1">No active {category} alerts at this time</p>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function MonitorDetailDialog({
  metric,
  obligationsData,
  receivablesData,
  onClose,
}: MonitorDetailDialogProps) {
  const navigate = useNavigate();
  const { alerts, isLoading, error, fetchAlerts } = useMonitorAlerts();

  // Fetch alerts when dialog opens
  useEffect(() => {
    if (metric) {
      fetchAlerts(metric);
    }
  }, [metric, fetchAlerts]);

  if (!metric) return null;

  const content = METRIC_CONTENT[metric];
  const currentStatus =
    metric === 'obligations' ? obligationsData?.status : receivablesData?.status;

  const handleAlertClick = (alertId: string) => {
    navigate(`/alerts/${alertId}/impact`);
    onClose();
  };

  return (
    <Dialog open={!!metric} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl">{content.title}</DialogTitle>
          <DialogDescription className="text-base font-medium text-gunmetal">
            {content.question}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {/* Current Status */}
          {currentStatus && (
            <div className="rounded-xl p-4 bg-muted/50">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-semibold text-gunmetal">Current Status:</span>
                <span
                  className={cn(
                    'px-2 py-0.5 rounded-full text-xs font-semibold uppercase',
                    currentStatus === 'covered' || currentStatus === 'healthy'
                      ? 'bg-lime/20 text-lime-700'
                      : currentStatus === 'tight' || currentStatus === 'watch'
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-tomato/20 text-tomato'
                  )}
                >
                  {currentStatus.replace('_', ' ')}
                </span>
              </div>
              {/* Metric-specific summary */}
              {metric === 'obligations' && obligationsData && (
                <p className="text-sm text-gray-600">
                  {obligationsData.covered_count} of {obligationsData.total_count} obligations
                  covered
                  {obligationsData.next_obligation_name && (
                    <span className="block mt-1 text-xs text-gray-500">
                      Next: {obligationsData.next_obligation_name} (
                      {obligationsData.next_obligation_amount_formatted}) in{' '}
                      {obligationsData.next_obligation_days}d
                    </span>
                  )}
                </p>
              )}
              {metric === 'receivables' && receivablesData && (
                <p className="text-sm text-gray-600">
                  {receivablesData.overdue_amount_formatted} overdue across{' '}
                  {receivablesData.overdue_count} invoices
                  {receivablesData.avg_days_late > 0 && (
                    <span className="block mt-1 text-xs text-gray-500">
                      Average {receivablesData.avg_days_late} days late
                    </span>
                  )}
                </p>
              )}
            </div>
          )}

          {/* Description */}
          <div>
            <h4 className="text-sm font-semibold text-gunmetal mb-1.5">What it measures</h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {content.whatItMeasures}
            </p>
          </div>

          {/* Thresholds */}
          <div>
            <h4 className="text-sm font-semibold text-gunmetal mb-2">Status Thresholds</h4>
            <div className="space-y-1.5">
              <div className="flex items-start gap-2">
                <span className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0 bg-lime" />
                <span className="text-sm text-muted-foreground">
                  <strong>{content.thresholds.good.label}</strong> —{' '}
                  {content.thresholds.good.description}
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0 bg-amber-400" />
                <span className="text-sm text-muted-foreground">
                  <strong>{content.thresholds.warning.label}</strong> —{' '}
                  {content.thresholds.warning.description}
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0 bg-tomato" />
                <span className="text-sm text-muted-foreground">
                  <strong>{content.thresholds.critical.label}</strong> —{' '}
                  {content.thresholds.critical.description}
                </span>
              </div>
            </div>
          </div>

          {/* Related Alerts */}
          <div>
            <h4 className="text-sm font-semibold text-gunmetal mb-3 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              Related Alerts
            </h4>

            {isLoading ? (
              <AlertsLoadingSkeleton />
            ) : error ? (
              <p className="text-sm text-tomato">{error}</p>
            ) : alerts.length === 0 ? (
              <NoAlertsState category={metric} />
            ) : (
              <div className="space-y-2">
                {alerts.map((alert) => (
                  <AlertCardCompact
                    key={alert.id}
                    alert={alert}
                    onClick={() => handleAlertClick(alert.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default MonitorDetailDialog;
