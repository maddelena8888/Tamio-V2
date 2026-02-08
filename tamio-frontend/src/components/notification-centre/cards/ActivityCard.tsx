import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import {
  AtSign,
  Share2,
  CheckSquare,
  ArrowRightLeft,
  User,
  GripVertical,
  X,
  Check,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DraggedNotificationItem } from '../NotificationCentreContext';

export type ActivityType = 'mention' | 'shared' | 'approval' | 'reconciliation';

export interface Activity {
  id: string;
  type: ActivityType;
  title: string;
  description: string;
  timestamp: string;
  read: boolean;
  actor?: {
    name: string;
    avatarUrl?: string;
  };
  actionUrl?: string;
  metadata?: Record<string, unknown>;
}

interface ActivityCardProps {
  activity: Activity;
  onDismiss?: (id: string) => void;
  onMarkRead?: (id: string) => void;
}

const typeConfig = {
  mention: {
    icon: AtSign,
    bgClass: 'bg-sky-500/10',
    borderClass: 'border-sky-500/20',
    textClass: 'text-sky-600',
    label: 'Mentioned you',
  },
  shared: {
    icon: Share2,
    bgClass: 'bg-purple-500/10',
    borderClass: 'border-purple-500/20',
    textClass: 'text-purple-600',
    label: 'Shared with you',
  },
  approval: {
    icon: CheckSquare,
    bgClass: 'bg-amber-500/10',
    borderClass: 'border-amber-500/20',
    textClass: 'text-amber-600',
    label: 'Needs approval',
  },
  reconciliation: {
    icon: ArrowRightLeft,
    bgClass: 'bg-lime/10',
    borderClass: 'border-lime/20',
    textClass: 'text-lime-700',
    label: 'Reconciliation',
  },
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

export function ActivityCard({ activity, onDismiss, onMarkRead }: ActivityCardProps) {
  const config = typeConfig[activity.type];
  const Icon = config.icon;

  const dragData: DraggedNotificationItem = {
    type: 'activity',
    id: activity.id,
    title: activity.title,
    description: activity.description,
    context: {
      activity_type: activity.type,
      actor: activity.actor,
      metadata: activity.metadata,
    },
  };

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `activity-${activity.id}`,
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
        activity.read ? 'bg-white/50 opacity-70' : 'bg-white',
        config.borderClass
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
            config.bgClass,
            'border',
            config.borderClass
          )}
        >
          <Icon className={cn('w-4 h-4', config.textClass)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              {!activity.read && (
                <span className={cn('w-2 h-2 rounded-full flex-shrink-0', config.textClass.replace('text-', 'bg-'))} />
              )}
              <span className="text-sm font-medium text-gunmetal truncate">
                {activity.title}
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              {formatTimeAgo(activity.timestamp)}
            </span>
          </div>

          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
            {activity.description}
          </p>

          {/* Actor badge */}
          {activity.actor && (
            <div className="flex items-center gap-1.5 mt-2">
              <div className="w-4 h-4 rounded-full bg-gray-100 flex items-center justify-center">
                {activity.actor.avatarUrl ? (
                  <img
                    src={activity.actor.avatarUrl}
                    alt={activity.actor.name}
                    className="w-4 h-4 rounded-full"
                  />
                ) : (
                  <User className="w-2.5 h-2.5 text-gray-400" />
                )}
              </div>
              <span className="text-xs text-muted-foreground">
                {activity.actor.name}
              </span>
            </div>
          )}
        </div>

        {/* Hover Actions */}
        <div className="absolute right-2 top-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {!activity.read && onMarkRead && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMarkRead(activity.id);
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
                onDismiss(activity.id);
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
