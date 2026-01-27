import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { CheckCircle, ArrowRight, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { dismissRisk, getSeverityStyles, type Risk, type RiskSeverity } from '@/lib/api/alertsActions';
import { formatAmount } from '@/lib/utils/decisionQueue';

// ============================================================================
// Types
// ============================================================================

export interface CriticalAlertsSectionProps {
  /** Critical alerts from API (max 3) */
  alerts: Risk[];
  /** Callback when an alert is dismissed */
  onDismissed?: (alertId: string) => void;
  /** Additional class names */
  className?: string;
}

// ============================================================================
// Sub-components
// ============================================================================

function SeverityBadge({ severity }: { severity: RiskSeverity }) {
  const styles = getSeverityStyles(severity);

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase',
        styles.bgClass,
        styles.textClass
      )}
    >
      {severity}
    </span>
  );
}

interface AlertCardProps {
  alert: Risk;
  onDismiss: (alertId: string) => Promise<void>;
  isDismissing: boolean;
}

function AlertCard({ alert, onDismiss, isDismissing }: AlertCardProps) {
  const navigate = useNavigate();
  const styles = getSeverityStyles(alert.severity);

  const handleViewImpact = () => {
    navigate(`/alerts/${alert.id}/impact`);
  };

  const handleDismiss = async () => {
    await onDismiss(alert.id);
  };

  return (
    <div
      className={cn(
        'rounded-2xl p-5 transition-all duration-200',
        'bg-gradient-to-r',
        alert.severity === 'urgent'
          ? 'from-tomato/10 to-white/60 border border-tomato/20'
          : alert.severity === 'high'
          ? 'from-amber-50 to-white/60 border border-amber-200/40'
          : 'from-lime/5 to-white/60 border border-lime/20'
      )}
    >
      <div className="space-y-3">
        {/* Severity badge */}
        <SeverityBadge severity={alert.severity} />

        {/* Title */}
        <h3 className="text-lg font-bold text-gunmetal">
          {alert.title}
        </h3>

        {/* Description / Impact statement */}
        <p className="text-sm text-muted-foreground">
          {alert.impact_statement || alert.primary_driver}
        </p>

        {/* Action buttons */}
        <div className="flex items-center gap-3 pt-2">
          <Button
            onClick={handleViewImpact}
            className="bg-tomato hover:bg-tomato/90 text-white"
            size="sm"
          >
            View Impact
          </Button>
          <Button
            onClick={handleDismiss}
            variant="outline"
            size="sm"
            disabled={isDismissing}
            className="border-gunmetal/20"
          >
            {isDismissing ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1" />
            ) : null}
            Dismiss
          </Button>
        </div>
      </div>
    </div>
  );
}

function AllClearCard() {
  return (
    <div className="rounded-2xl p-8 bg-gradient-to-r from-lime/10 to-white/60 border border-lime/20 text-center">
      <CheckCircle className="w-12 h-12 text-lime mx-auto mb-4" />
      <h3 className="text-xl font-bold text-gunmetal mb-2">
        All Clear
      </h3>
      <p className="text-sm text-muted-foreground">
        No critical alerts at this time
      </p>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function CriticalAlertsSection({
  alerts,
  onDismissed,
  className,
}: CriticalAlertsSectionProps) {
  const [dismissingIds, setDismissingIds] = useState<Set<string>>(new Set());
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  const handleDismiss = async (alertId: string) => {
    setDismissingIds(prev => new Set(prev).add(alertId));
    try {
      await dismissRisk(alertId);
      setDismissedIds(prev => new Set(prev).add(alertId));
      onDismissed?.(alertId);
    } finally {
      setDismissingIds(prev => {
        const next = new Set(prev);
        next.delete(alertId);
        return next;
      });
    }
  };

  // Filter to only urgent and high severity alerts, excluding dismissed
  const visibleAlerts = alerts.filter(
    a => !dismissedIds.has(a.id) && (a.severity === 'urgent' || a.severity === 'high')
  );

  // Show only the first (highest priority) alert
  const currentAlert = visibleAlerts.length > 0 ? visibleAlerts[0] : null;

  return (
    <section className={cn('mt-4', className)}>
      {/* Section header */}
      <h2 className="text-2xl font-bold text-gunmetal mb-6">
        Critical Alerts
      </h2>

      {/* Show one alert at a time or All Clear state */}
      {currentAlert ? (
        <AlertCard
          key={currentAlert.id}
          alert={currentAlert}
          onDismiss={handleDismiss}
          isDismissing={dismissingIds.has(currentAlert.id)}
        />
      ) : (
        <AllClearCard />
      )}

      {/* View all alerts link */}
      <div className="mt-6">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-sm font-medium text-gunmetal hover:text-gunmetal/70 transition-colors"
        >
          View all alerts
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </section>
  );
}

export default CriticalAlertsSection;
