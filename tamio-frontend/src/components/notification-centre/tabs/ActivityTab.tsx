import { useState, useEffect } from 'react';
import { Activity as ActivityIcon, CheckCircle2 } from 'lucide-react';
import { ActivityCard, type Activity, type ActivityType } from '../cards/ActivityCard';
import { useNotificationCentre } from '../NotificationCentreContext';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// Mock data - replace with real API calls
const mockActivities: Activity[] = [
  {
    id: 'act-1',
    type: 'approval',
    title: 'Payment batch ready',
    description: '3 vendor payments totaling $12,450 need your approval before Friday',
    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 min ago
    read: false,
    actor: { name: 'TAMI' },
    metadata: { batchId: 'batch-123', totalAmount: 12450 },
  },
  {
    id: 'act-2',
    type: 'mention',
    title: 'Sarah mentioned you',
    description: 'in "Q2 Hiring Scenario" - "Can you review the salary assumptions?"',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    read: false,
    actor: { name: 'Sarah Chen' },
    metadata: { scenarioId: 'scenario-456' },
  },
  {
    id: 'act-3',
    type: 'reconciliation',
    title: 'Transaction needs review',
    description: 'Bank payment of $8,200 matched to RetailCo invoice with 5% variance',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(), // 4 hours ago
    read: false,
    metadata: { transactionId: 'txn-789', variance: 5 },
  },
  {
    id: 'act-4',
    type: 'shared',
    title: 'Mike shared a scenario',
    description: '"Client Loss - TechCorp" scenario was shared with you for review',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
    read: true,
    actor: { name: 'Mike Johnson' },
    metadata: { scenarioId: 'scenario-abc' },
  },
  {
    id: 'act-5',
    type: 'approval',
    title: 'Invoice follow-up approved',
    description: 'Follow-up email to DataTech has been sent automatically',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(), // 2 days ago
    read: true,
    actor: { name: 'TAMI' },
  },
];

const typeLabels: Record<ActivityType, { label: string; bgClass: string; textClass: string }> = {
  approval: { label: 'Pending Approvals', bgClass: 'bg-amber-500/5', textClass: 'text-amber-600' },
  mention: { label: 'Mentions', bgClass: 'bg-sky-500/5', textClass: 'text-sky-600' },
  shared: { label: 'Shared With You', bgClass: 'bg-purple-500/5', textClass: 'text-purple-600' },
  reconciliation: { label: 'Reconciliation', bgClass: 'bg-lime/5', textClass: 'text-lime-700' },
};

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
        <CheckCircle2 className="w-6 h-6 text-gray-400" />
      </div>
      <h3 className="text-sm font-semibold text-gunmetal mb-1">All caught up!</h3>
      <p className="text-xs text-muted-foreground max-w-[250px]">
        No pending activity. Team mentions, shared items, and approvals will appear here.
      </p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="p-3 rounded-xl border border-gray-100">
          <div className="flex gap-3">
            <Skeleton className="w-8 h-8 rounded-lg" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-full" />
              <div className="flex items-center gap-1.5">
                <Skeleton className="w-4 h-4 rounded-full" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ActivityTab() {
  const { setUnreadCounts, unreadCounts } = useNotificationCentre();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate API call - replace with real API
    async function fetchActivities() {
      // TODO: Replace with actual API call
      // const response = await fetch('/api/activity/feed');
      // const data = await response.json();
      // setActivities(data.activities);

      // Using mock data for now
      await new Promise((resolve) => setTimeout(resolve, 500));
      setActivities(mockActivities);

      // Update unread count
      const unreadCount = mockActivities.filter((a) => !a.read).length;
      setUnreadCounts({
        ...unreadCounts,
        activity: unreadCount,
      });

      setIsLoading(false);
    }

    fetchActivities();
  }, []);

  const handleDismiss = (id: string) => {
    const activity = activities.find((a) => a.id === id);
    setActivities((prev) => prev.filter((a) => a.id !== id));

    // Update unread count if dismissed item was unread
    if (activity && !activity.read) {
      setUnreadCounts({
        ...unreadCounts,
        activity: Math.max(0, unreadCounts.activity - 1),
      });
    }
  };

  const handleMarkRead = (id: string) => {
    setActivities((prev) =>
      prev.map((a) => (a.id === id ? { ...a, read: true } : a))
    );
    setUnreadCounts({
      ...unreadCounts,
      activity: Math.max(0, unreadCounts.activity - 1),
    });
  };

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  if (activities.length === 0) {
    return <EmptyState />;
  }

  // Group activities by type, prioritizing unread
  const unreadActivities = activities.filter((a) => !a.read);
  const readActivities = activities.filter((a) => a.read);

  // Group unread by type
  const groupedUnread = unreadActivities.reduce((acc, activity) => {
    if (!acc[activity.type]) {
      acc[activity.type] = [];
    }
    acc[activity.type].push(activity);
    return acc;
  }, {} as Record<ActivityType, Activity[]>);

  const typeOrder: ActivityType[] = ['approval', 'mention', 'reconciliation', 'shared'];

  return (
    <div className="space-y-4">
      {/* Unread activities grouped by type */}
      {typeOrder.map((type) => {
        const group = groupedUnread[type];
        if (!group || group.length === 0) return null;

        const config = typeLabels[type];

        return (
          <div key={type}>
            <div className={cn('px-3 py-1.5 rounded-lg mb-2', config.bgClass)}>
              <div className="flex items-center gap-2">
                <ActivityIcon className={cn('w-3.5 h-3.5', config.textClass)} />
                <span className={cn('text-xs font-medium uppercase tracking-wide', config.textClass)}>
                  {config.label}
                </span>
                <span className={cn('text-xs', config.textClass)}>
                  ({group.length})
                </span>
              </div>
            </div>
            <div className="space-y-2">
              {group.map((activity) => (
                <ActivityCard
                  key={activity.id}
                  activity={activity}
                  onDismiss={handleDismiss}
                  onMarkRead={handleMarkRead}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Read activities */}
      {readActivities.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-gray-50">
            <div className="flex items-center gap-2">
              <ActivityIcon className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Earlier
              </span>
              <span className="text-xs text-gray-400">
                ({readActivities.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {readActivities.map((activity) => (
              <ActivityCard
                key={activity.id}
                activity={activity}
                onDismiss={handleDismiss}
                onMarkRead={handleMarkRead}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
