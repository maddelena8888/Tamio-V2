import { useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  DndContext,
  DragOverlay,
  useSensor,
  useSensors,
  PointerSensor,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import { useNotificationCentre, type DraggedNotificationItem } from './NotificationCentreContext';
import { AlertsTab } from './tabs/AlertsTab';
import { ActivityTab } from './tabs/ActivityTab';
import { RulesTab } from './tabs/RulesTab';
import { TAMIDropZone } from './TAMIDropZone';
import { AlertTriangle, Activity, Gauge } from 'lucide-react';
import { cn } from '@/lib/utils';

function DragPreview({ item }: { item: DraggedNotificationItem }) {
  return (
    <div className="bg-white/95 backdrop-blur-sm border border-lime shadow-lg rounded-xl p-3 max-w-[300px]">
      <p className="text-sm font-medium text-gunmetal truncate">{item.title}</p>
      {item.description && (
        <p className="text-xs text-muted-foreground truncate mt-0.5">{item.description}</p>
      )}
    </div>
  );
}

export function NotificationCentre() {
  const {
    isOpen,
    close,
    activeTab,
    setActiveTab,
    unreadCounts,
    draggedItem,
    setDraggedItem,
    setDroppedItem,
  } = useNotificationCentre();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    const data = event.active.data.current as DraggedNotificationItem;
    setDraggedItem(data);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over?.id === 'tami-drop-zone' && active.data.current) {
      setDroppedItem(active.data.current as DraggedNotificationItem);
    }

    setDraggedItem(null);
  };

  const handleDragCancel = () => {
    setDraggedItem(null);
  };

  const totalUnread = unreadCounts.alerts + unreadCounts.activity + unreadCounts.rules;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && close()}>
      <DialogContent className="max-w-[600px] h-[70vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b border-gunmetal/10 flex-shrink-0">
          <DialogTitle className="flex items-center gap-2 font-league-spartan">
            Notification Centre
            {totalUnread > 0 && (
              <Badge variant="secondary" className="bg-tomato/10 text-tomato">
                {totalUnread}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>

        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <div className="flex flex-col flex-1 min-h-0">
            <Tabs
              value={activeTab}
              onValueChange={(value) => setActiveTab(value as typeof activeTab)}
              className="flex flex-col flex-1 min-h-0"
            >
              <TabsList className="mx-6 mt-4 mb-2 w-fit">
                <TabsTrigger value="alerts" className="gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Alerts
                  {unreadCounts.alerts > 0 && (
                    <Badge
                      variant="secondary"
                      className={cn(
                        'ml-1 h-5 min-w-[20px] px-1.5 text-[10px]',
                        activeTab === 'alerts'
                          ? 'bg-tomato/10 text-tomato'
                          : 'bg-gray-100 text-gray-500'
                      )}
                    >
                      {unreadCounts.alerts}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="activity" className="gap-1.5">
                  <Activity className="w-3.5 h-3.5" />
                  Activity
                  {unreadCounts.activity > 0 && (
                    <Badge
                      variant="secondary"
                      className={cn(
                        'ml-1 h-5 min-w-[20px] px-1.5 text-[10px]',
                        activeTab === 'activity'
                          ? 'bg-sky-500/10 text-sky-600'
                          : 'bg-gray-100 text-gray-500'
                      )}
                    >
                      {unreadCounts.activity}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="rules" className="gap-1.5">
                  <Gauge className="w-3.5 h-3.5" />
                  Rules
                  {unreadCounts.rules > 0 && (
                    <Badge
                      variant="secondary"
                      className={cn(
                        'ml-1 h-5 min-w-[20px] px-1.5 text-[10px]',
                        activeTab === 'rules'
                          ? 'bg-amber-500/10 text-amber-600'
                          : 'bg-gray-100 text-gray-500'
                      )}
                    >
                      {unreadCounts.rules}
                    </Badge>
                  )}
                </TabsTrigger>
              </TabsList>

              <div className="flex-1 min-h-0 overflow-hidden">
                <ScrollArea className="h-full">
                  <TabsContent value="alerts" className="m-0 px-6 pb-4">
                    <AlertsTab />
                  </TabsContent>
                  <TabsContent value="activity" className="m-0 px-6 pb-4">
                    <ActivityTab />
                  </TabsContent>
                  <TabsContent value="rules" className="m-0 px-6 pb-4">
                    <RulesTab />
                  </TabsContent>
                </ScrollArea>
              </div>
            </Tabs>

            <TAMIDropZone />
          </div>

          <DragOverlay>
            {draggedItem && <DragPreview item={draggedItem} />}
          </DragOverlay>
        </DndContext>
      </DialogContent>
    </Dialog>
  );
}
