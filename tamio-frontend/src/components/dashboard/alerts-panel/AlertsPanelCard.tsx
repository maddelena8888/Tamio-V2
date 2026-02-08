/**
 * AlertsPanelCard Component
 *
 * Compact alert card for the dashboard horizontal scroll panel.
 * Shows essential info: severity, due date, title, impact, and quick actions.
 */

import {
  Clock,
  AlertCircle,
  AlertTriangle,
  Bell,
  CheckCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getSeverityStyles } from '@/lib/api/alertsActions';
import { formatAmount } from '@/lib/utils/decisionQueue';
import type { AlertPanelItem } from './types';

interface AlertsPanelCardProps {
  item: AlertPanelItem;
  onClick: (item: AlertPanelItem) => void;
}

/**
 * Get severity icon based on severity level
 */
function SeverityIcon({ severity }: { severity: 'urgent' | 'high' | 'normal' }) {
  const styles = getSeverityStyles(severity);

  switch (severity) {
    case 'urgent':
      return <AlertCircle className={cn('w-4 h-4', styles.textClass)} />;
    case 'high':
      return <AlertTriangle className={cn('w-4 h-4', styles.textClass)} />;
    default:
      return <Bell className={cn('w-4 h-4', styles.textClass)} />;
  }
}

/**
 * Get label text for severity
 */
function getSeverityLabel(severity: 'urgent' | 'high' | 'normal'): string {
  switch (severity) {
    case 'urgent':
      return 'Urgent';
    case 'high':
      return 'High';
    default:
      return 'FYI';
  }
}

/**
 * Get status indicator for section
 */
function SectionIndicator({ section }: { section: AlertPanelItem['section'] }) {
  if (section === 'being_handled') {
    return (
      <div className="flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
        <CheckCircle className="w-3 h-3" />
        <span>In Progress</span>
      </div>
    );
  }
  return null;
}

export function AlertsPanelCard({
  item,
  onClick,
}: AlertsPanelCardProps) {
  const { alert, section } = item;
  const styles = getSeverityStyles(alert.severity);

  // Get glassmorphic background color based on severity
  const getBackgroundColor = () => {
    if (section === 'requires_decision') {
      switch (alert.severity) {
        case 'urgent':
          return 'bg-tomato/20';
        case 'high':
          return 'bg-amber-500/18';
        default:
          return 'bg-lime/15';
      }
    }
    if (section === 'being_handled') {
      return 'bg-blue-500/15';
    }
    return 'bg-lime/12';
  };

  return (
    <div
      className={cn(
        // Glassomorphic base
        'flex flex-col p-5 rounded-2xl',
        'backdrop-blur-xl bg-white/50',
        'border border-white/60',
        'shadow-[inset_0_1px_1px_rgba(255,255,255,0.8),0_4px_16px_rgba(0,0,0,0.06)]',
        // Card dimensions
        'w-[340px] h-[160px] flex-shrink-0',
        // Hover effects
        'hover:bg-white/60 hover:shadow-[inset_0_1px_1px_rgba(255,255,255,0.9),0_8px_24px_rgba(0,0,0,0.1)]',
        'hover:scale-[1.02] transition-all duration-300 ease-out',
        'cursor-pointer group',
        // Urgency background color
        getBackgroundColor()
      )}
      onClick={() => onClick(item)}
    >
      {/* Header: Severity badge + Due date */}
      <div className="flex items-center justify-between mb-3">
        <div className={cn(
          'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold',
          'backdrop-blur-sm shadow-sm',
          styles.bgClass, styles.textClass
        )}>
          <SeverityIcon severity={alert.severity} />
          <span>{getSeverityLabel(alert.severity)}</span>
        </div>

        <div className="flex items-center gap-1.5 text-xs text-gray-500 bg-white/40 px-2.5 py-1 rounded-full backdrop-blur-sm">
          <Clock className="w-3.5 h-3.5" />
          <span>{alert.due_horizon_label || 'No deadline'}</span>
        </div>
      </div>

      {/* Section indicator for being_handled */}
      {section === 'being_handled' && (
        <div className="mb-2">
          <SectionIndicator section={section} />
        </div>
      )}

      {/* Title */}
      <h4 className="font-semibold text-gunmetal text-[15px] leading-snug line-clamp-3 flex-grow">
        {alert.title}
      </h4>

      {/* Cash impact */}
      {alert.cash_impact && (
        <div className="flex items-center gap-1.5 mt-auto">
          <span className={cn('text-base font-bold', styles.textClass)}>
            {formatAmount(Math.abs(alert.cash_impact))}
          </span>
          <span className="text-sm text-gray-500">at risk</span>
        </div>
      )}
    </div>
  );
}
