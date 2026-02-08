import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type NotificationTab = 'alerts' | 'activity' | 'rules';

export interface DraggedNotificationItem {
  type: 'alert' | 'activity' | 'rule';
  id: string;
  title: string;
  description?: string;
  context: Record<string, unknown>;
}

interface NotificationCentreContextValue {
  // Modal state
  isOpen: boolean;
  open: (tab?: NotificationTab) => void;
  close: () => void;

  // Tab state
  activeTab: NotificationTab;
  setActiveTab: (tab: NotificationTab) => void;

  // Unread counts
  unreadCounts: {
    alerts: number;
    activity: number;
    rules: number;
  };
  setUnreadCounts: (counts: { alerts: number; activity: number; rules: number }) => void;

  // Drag state for TAMI integration
  draggedItem: DraggedNotificationItem | null;
  setDraggedItem: (item: DraggedNotificationItem | null) => void;

  // Dropped item for TAMI input
  droppedItem: DraggedNotificationItem | null;
  setDroppedItem: (item: DraggedNotificationItem | null) => void;
}

const NotificationCentreContext = createContext<NotificationCentreContextValue | null>(null);

export function NotificationCentreProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<NotificationTab>('alerts');
  const [unreadCounts, setUnreadCounts] = useState({ alerts: 0, activity: 0, rules: 0 });
  const [draggedItem, setDraggedItem] = useState<DraggedNotificationItem | null>(null);
  const [droppedItem, setDroppedItem] = useState<DraggedNotificationItem | null>(null);

  const open = useCallback((tab?: NotificationTab) => {
    if (tab) setActiveTab(tab);
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setDraggedItem(null);
  }, []);

  return (
    <NotificationCentreContext.Provider
      value={{
        isOpen,
        open,
        close,
        activeTab,
        setActiveTab,
        unreadCounts,
        setUnreadCounts,
        draggedItem,
        setDraggedItem,
        droppedItem,
        setDroppedItem,
      }}
    >
      {children}
    </NotificationCentreContext.Provider>
  );
}

export function useNotificationCentre() {
  const context = useContext(NotificationCentreContext);
  if (!context) {
    throw new Error('useNotificationCentre must be used within NotificationCentreProvider');
  }
  return context;
}
