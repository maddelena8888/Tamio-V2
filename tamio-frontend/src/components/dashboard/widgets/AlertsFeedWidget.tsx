/**
 * Alerts & Actions Widget
 *
 * Shows feed of items needing attention, prioritized by urgency.
 * "Act Now" vs "Monitor" categorization.
 */

import { Link } from 'react-router-dom';
import { AlertCircle, AlertTriangle, Bell, CheckCircle } from 'lucide-react';
import { useWidgetData } from '@/hooks/useDashboardData';
import { cn } from '@/lib/utils';
import { WidgetSkeleton } from './WidgetSkeleton';
import type { WidgetProps } from './types';

export function AlertsFeedWidget({ settings, className }: WidgetProps) {
  const { healthData, risksData, isLoading } = useWidgetData();
  const maxItems = (settings?.maxItems as number) || 5;

  if (isLoading) {
    return <WidgetSkeleton className={className} />;
  }

  // Combine critical alerts from health data with risks data
  const alerts = healthData?.critical_alerts || risksData || [];

  if (alerts.length === 0) {
    return (
      <div className={cn('flex flex-col h-full items-center justify-center', className)}>
        <CheckCircle className="w-10 h-10 text-lime-600 mb-2" />
        <span className="text-lg font-semibold text-lime-700">All Clear</span>
        <span className="text-xs text-muted-foreground mt-1">No alerts at this time</span>
      </div>
    );
  }

  // Take only the configured number of items
  const displayAlerts = alerts.slice(0, maxItems);

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Alerts
          </span>
        </div>
        {alerts.length > maxItems && (
          <span className="text-xs text-muted-foreground">
            +{alerts.length - maxItems} more
          </span>
        )}
      </div>

      {/* Alert List */}
      <div className="flex-1 flex flex-col gap-2 overflow-hidden">
        {displayAlerts.map((alert, index) => (
          <AlertItem key={alert.id || index} alert={alert} />
        ))}
      </div>

      {/* Action Link */}
      <div className="flex justify-center pt-3">
        <Link to="/alerts" className="text-xs text-gunmetal hover:underline">
          View all alerts &rarr;
        </Link>
      </div>
    </div>
  );
}

// ============================================================================
// Alert Item Component
// ============================================================================

interface AlertItemProps {
  alert: {
    id?: string;
    title: string;
    severity: 'urgent' | 'high' | 'medium' | 'normal';
    impact_statement?: string | null;
  };
}

function AlertItem({ alert }: AlertItemProps) {
  const severityConfig = {
    urgent: {
      icon: AlertCircle,
      bgClass: 'bg-tomato/15',
      iconBgClass: 'bg-white/60',
      iconClass: 'text-tomato',
    },
    high: {
      icon: AlertTriangle,
      bgClass: 'bg-amber-500/15',
      iconBgClass: 'bg-white/60',
      iconClass: 'text-amber-600',
    },
    medium: {
      icon: AlertTriangle,
      bgClass: 'bg-amber-500/10',
      iconBgClass: 'bg-white/60',
      iconClass: 'text-amber-500',
    },
    normal: {
      icon: Bell,
      bgClass: 'bg-lime/10',
      iconBgClass: 'bg-white/60',
      iconClass: 'text-lime-dark',
    },
  };

  const config = severityConfig[alert.severity] || severityConfig.normal;
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'flex items-start gap-2 p-2.5 rounded-xl',
        'backdrop-blur-sm border border-white/30',
        'shadow-[inset_0_1px_1px_rgba(255,255,255,0.5),0_1px_4px_rgba(0,0,0,0.04)]',
        'transition-all duration-200 hover:shadow-[inset_0_1px_1px_rgba(255,255,255,0.7),0_2px_6px_rgba(0,0,0,0.08)]',
        config.bgClass
      )}
    >
      <div className={cn('w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0', config.iconBgClass)}>
        <Icon className={cn('w-3.5 h-3.5', config.iconClass)} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gunmetal line-clamp-1">{alert.title}</p>
        {alert.impact_statement && (
          <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
            {alert.impact_statement}
          </p>
        )}
      </div>
    </div>
  );
}
