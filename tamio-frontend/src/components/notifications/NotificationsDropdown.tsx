import { useState } from 'react';
import {
  Bell,
  AlertTriangle,
  AtSign,
  Zap,
  Check,
  X,
  ChevronRight,
} from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { useNotificationCentre } from '@/components/notification-centre';

export type NotificationUrgency = 'critical' | 'warning' | 'info';
export type NotificationType = 'alert' | 'mention' | 'unusual';

export interface Notification {
  id: string;
  type: NotificationType;
  urgency: NotificationUrgency;
  title: string;
  description: string;
  timestamp: string;
  read: boolean;
  actionUrl?: string;
}

// Mock notifications data
const mockNotifications: Notification[] = [
  {
    id: '1',
    type: 'alert',
    urgency: 'critical',
    title: 'Cash buffer rule breached',
    description: 'Available cash dropped below 2-month runway threshold',
    timestamp: '5 min ago',
    read: false,
  },
  {
    id: '2',
    type: 'mention',
    urgency: 'info',
    title: 'Sarah mentioned you',
    description: 'in "Q2 Hiring Scenario" - "Can you review the salary assumptions?"',
    timestamp: '1 hour ago',
    read: false,
  },
  {
    id: '3',
    type: 'unusual',
    urgency: 'warning',
    title: 'Unusual expense detected',
    description: 'AWS charges 47% higher than 30-day average',
    timestamp: '3 hours ago',
    read: false,
  },
  {
    id: '4',
    type: 'alert',
    urgency: 'warning',
    title: 'Payment overdue',
    description: 'RetailCo invoice #1042 is 14 days past due',
    timestamp: '1 day ago',
    read: true,
  },
  {
    id: '5',
    type: 'mention',
    urgency: 'info',
    title: 'Mike shared a scenario',
    description: '"Client Loss - TechCorp" scenario was shared with you',
    timestamp: '2 days ago',
    read: true,
  },
];

const urgencyConfig = {
  critical: {
    dot: 'bg-tomato',
    bg: 'bg-tomato/10',
    border: 'border-tomato/20',
    text: 'text-tomato',
  },
  warning: {
    dot: 'bg-amber-500',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    text: 'text-amber-600',
  },
  info: {
    dot: 'bg-sky-500',
    bg: 'bg-sky-500/10',
    border: 'border-sky-500/20',
    text: 'text-sky-600',
  },
};

const typeIcons = {
  alert: AlertTriangle,
  mention: AtSign,
  unusual: Zap,
};

interface NotificationItemProps {
  notification: Notification;
  onMarkRead: (id: string) => void;
  onDismiss: (id: string) => void;
  onClick: (notification: Notification) => void;
}

function NotificationItem({ notification, onMarkRead, onDismiss, onClick }: NotificationItemProps) {
  const config = urgencyConfig[notification.urgency];
  const Icon = typeIcons[notification.type];

  return (
    <div
      className={cn(
        'relative px-3 py-3 border-b border-gunmetal/5 last:border-0 transition-colors group cursor-pointer',
        !notification.read && config.bg,
        notification.read && 'opacity-60 hover:opacity-100'
      )}
      onClick={() => onClick(notification)}
    >
      <div className="flex gap-3">
        {/* Icon */}
        <div
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
            config.bg,
            'border',
            config.border
          )}
        >
          <Icon className={cn('w-4 h-4', config.text)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              {!notification.read && (
                <span className={cn('w-2 h-2 rounded-full flex-shrink-0', config.dot)} />
              )}
              <span className="text-sm font-medium text-gunmetal truncate">
                {notification.title}
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              {notification.timestamp}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
            {notification.description}
          </p>
        </div>

        {/* Hover Actions */}
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {!notification.read && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMarkRead(notification.id);
              }}
              className="w-6 h-6 rounded-md bg-white hover:bg-lime-dark/10 flex items-center justify-center text-muted-foreground hover:text-lime-dark transition-colors"
              title="Mark as read"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDismiss(notification.id);
            }}
            className="w-6 h-6 rounded-md bg-white hover:bg-tomato/10 flex items-center justify-center text-muted-foreground hover:text-tomato transition-colors"
            title="Dismiss"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

interface NotificationsDropdownProps {
  onNotificationClick?: (notification: Notification) => void;
}

export function NotificationsDropdown({ onNotificationClick }: NotificationsDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>(mockNotifications);
  const { open: openNotificationCentre } = useNotificationCentre();

  const unreadCount = notifications.filter((n) => !n.read).length;

  const handleMarkRead = (id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const handleDismiss = (id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const handleNotificationClick = (notification: Notification) => {
    handleMarkRead(notification.id);
    onNotificationClick?.(notification);
    setIsOpen(false);
  };

  // Group notifications by urgency
  const criticalNotifications = notifications.filter((n) => n.urgency === 'critical' && !n.read);
  const otherNotifications = notifications.filter(
    (n) => !(n.urgency === 'critical' && !n.read)
  );

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button
          className="w-9 h-9 rounded-lg bg-white/50 text-muted-foreground cursor-pointer flex items-center justify-center relative transition-all hover:bg-white hover:text-gunmetal border border-white/20"
        >
          <Bell className="w-[18px] h-[18px]" />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 w-4 h-4 bg-tomato rounded-full text-[10px] font-semibold flex items-center justify-center text-white">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-96 p-0 bg-white/95 backdrop-blur-sm border-gunmetal/10"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gunmetal/10">
          <h3 className="font-semibold text-gunmetal">Notifications</h3>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="text-xs text-muted-foreground hover:text-gunmetal transition-colors"
            >
              Mark all read
            </button>
          )}
        </div>

        {/* Notifications List */}
        <div className="max-h-[400px] overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No notifications</p>
            </div>
          ) : (
            <>
              {/* Critical notifications first */}
              {criticalNotifications.length > 0 && (
                <div className="border-b border-tomato/20">
                  <div className="px-4 py-2 bg-tomato/5">
                    <span className="text-[10px] uppercase tracking-wider font-medium text-tomato">
                      Requires Attention
                    </span>
                  </div>
                  {criticalNotifications.map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                      onMarkRead={handleMarkRead}
                      onDismiss={handleDismiss}
                      onClick={handleNotificationClick}
                    />
                  ))}
                </div>
              )}

              {/* Other notifications */}
              {otherNotifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onMarkRead={handleMarkRead}
                  onDismiss={handleDismiss}
                  onClick={handleNotificationClick}
                />
              ))}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gunmetal/10 p-2">
          <button
            onClick={() => {
              setIsOpen(false);
              openNotificationCentre();
            }}
            className="w-full flex items-center justify-center gap-1 px-4 py-2 rounded-lg hover:bg-gunmetal/5 text-sm text-muted-foreground hover:text-gunmetal transition-colors"
          >
            View all notifications
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
