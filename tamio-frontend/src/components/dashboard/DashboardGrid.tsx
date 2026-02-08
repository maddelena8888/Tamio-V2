/**
 * Dashboard Grid - Main draggable grid container with @dnd-kit
 *
 * Provides:
 * - Responsive grid layout (1-3 columns)
 * - Drag-and-drop reordering
 * - Empty state when no widgets
 */

import { useState, useCallback } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  rectSortingStrategy,
} from '@dnd-kit/sortable';
import { useDashboard } from '@/contexts/DashboardContext';
import { DashboardCard } from './DashboardCard';
import { EmptyDashboard } from './EmptyDashboard';
import { cn } from '@/lib/utils';

interface DashboardGridProps {
  className?: string;
}

export function DashboardGrid({ className }: DashboardGridProps) {
  const { widgets, reorderWidgets } = useDashboard();
  const [activeId, setActiveId] = useState<string | null>(null);

  // Configure sensors for drag detection
  const sensors = useSensors(
    useSensor(PointerSensor, {
      // Require pointer to move 8px before activating drag
      activationConstraint: { distance: 8 },
    }),
    useSensor(KeyboardSensor)
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      setActiveId(null);

      if (over && active.id !== over.id) {
        const oldIndex = widgets.findIndex((w) => w.id === active.id);
        const newIndex = widgets.findIndex((w) => w.id === over.id);

        if (oldIndex !== -1 && newIndex !== -1) {
          reorderWidgets(oldIndex, newIndex);
        }
      }
    },
    [widgets, reorderWidgets]
  );

  // Show empty state when no widgets
  if (widgets.length === 0) {
    return <EmptyDashboard />;
  }

  const activeWidget = activeId ? widgets.find((w) => w.id === activeId) : null;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={widgets.map((w) => w.id)} strategy={rectSortingStrategy}>
        <div
          className={cn(
            'grid gap-4 md:gap-6',
            // Responsive columns: 1 on mobile, 2 on tablet, 3 on desktop
            'grid-cols-1 md:grid-cols-2 xl:grid-cols-3',
            className
          )}
        >
          {widgets.map((widget) => (
            <DashboardCard key={widget.id} widget={widget} />
          ))}
        </div>
      </SortableContext>

      {/* Drag overlay for visual feedback */}
      <DragOverlay>
        {activeWidget && (
          <DashboardCard widget={activeWidget} isDragOverlay />
        )}
      </DragOverlay>
    </DndContext>
  );
}
