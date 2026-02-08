import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { AlertTriangle, AlertCircle, Bell, X, Check, GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import { type Risk, type RiskSeverity, getSeverityStyles } from '@/lib/api/alertsActions';
import type { DraggedNotificationItem } from '../NotificationCentreContext';

interface AlertCardProps {
  risk: Risk;
  onDismiss?: (id: string) => void;
  onMarkRead?: (id: string) => void;
  isRead?: boolean;
}

const severityIcons = {
  urgent: AlertCircle,
  high: AlertTriangle,
  normal: Bell,
};

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount);
}

export function AlertCard({ risk, onDismiss, onMarkRead, isRead = false }: AlertCardProps) {
  const styles = getSeverityStyles(risk.severity);
  const Icon = severityIcons[risk.severity];

  const dragData: DraggedNotificationItem = {
    type: 'alert',
    id: risk.id,
    title: risk.title,
    description: risk.primary_driver,
    context: {
      severity: risk.severity,
      cash_impact: risk.cash_impact,
      deadline: risk.deadline,
      detection_type: risk.detection_type,
      impact_statement: risk.impact_statement,
    },
  };

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `alert-${risk.id}`,
    data: dragData,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'relative p-3 rounded-xl border transition-all group',
        isDragging && 'opacity-50 shadow-lg z-50',
        isRead ? 'bg-white/50 opacity-70' : 'bg-white',
        styles.borderClass
      )}
    >
      {/* Drag handle */}
      <div
        {...listeners}
        {...attributes}
        className="absolute left-1 top-1/2 -translate-y-1/2 p-1 cursor-grab opacity-0 group-hover:opacity-100 transition-opacity text-gray-300 hover:text-gray-500"
      >
        <GripVertical className="w-4 h-4" />
      </div>

      <div className="flex gap-3 pl-4">
        {/* Icon */}
        <div
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
            styles.bgClass,
            'border',
            styles.borderClass
          )}
        >
          <Icon className={cn('w-4 h-4', styles.textClass)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              {!isRead && (
                <span className={cn('w-2 h-2 rounded-full flex-shrink-0', styles.textClass.replace('text-', 'bg-'))} />
              )}
              <span className="text-sm font-medium text-gunmetal truncate">
                {risk.title}
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              {formatTimeAgo(risk.detected_at)}
            </span>
          </div>

          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
            {risk.primary_driver}
          </p>

          {/* Impact badge */}
          {risk.cash_impact && (
            <div className="flex items-center gap-2 mt-2">
              <span className={cn('text-xs font-medium px-2 py-0.5 rounded-full', styles.bgClass, styles.textClass)}>
                {formatCurrency(risk.cash_impact)} impact
              </span>
              {risk.due_horizon_label && (
                <span className="text-xs text-muted-foreground">
                  {risk.due_horizon_label}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Hover Actions */}
        <div className="absolute right-2 top-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {!isRead && onMarkRead && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMarkRead(risk.id);
              }}
              className="w-6 h-6 rounded-md bg-white hover:bg-lime/10 flex items-center justify-center text-muted-foreground hover:text-lime-dark transition-colors shadow-sm border border-gray-100"
              title="Mark as read"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
          )}
          {onDismiss && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDismiss(risk.id);
              }}
              className="w-6 h-6 rounded-md bg-white hover:bg-tomato/10 flex items-center justify-center text-muted-foreground hover:text-tomato transition-colors shadow-sm border border-gray-100"
              title="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
