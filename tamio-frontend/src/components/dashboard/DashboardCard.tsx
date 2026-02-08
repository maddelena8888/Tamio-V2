/**
 * Dashboard Card - Sortable card wrapper with drag handle and menu
 *
 * Each card displays:
 * - Drag handle (GripVertical icon)
 * - Widget title
 * - Action menu (⋮)
 * - Widget content
 */

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';
import { NeuroCard } from '@/components/ui/neuro-card';
import { WIDGET_REGISTRY } from './widgets/registry';
import { DashboardCardMenu } from './DashboardCardMenu';
import { useDashboard } from '@/contexts/DashboardContext';
import { cn } from '@/lib/utils';
import type { WidgetConfig } from './widgets/types';

interface DashboardCardProps {
  widget: WidgetConfig;
  isDragOverlay?: boolean;
}

export function DashboardCard({ widget, isDragOverlay = false }: DashboardCardProps) {
  const { removeWidget } = useDashboard();
  const widgetDef = WIDGET_REGISTRY[widget.widgetId];

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: widget.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  // Fallback if widget not found in registry
  if (!widgetDef) {
    return null;
  }

  const WidgetComponent = widgetDef.component;

  const handleRemove = () => {
    removeWidget(widget.id);
  };

  const handleConfigure = () => {
    // For now, just log - would open a config modal in full implementation
    console.log('Configure widget:', widget.id);
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        isDragging && !isDragOverlay && 'opacity-50',
        isDragOverlay && 'shadow-2xl rotate-2 scale-105'
      )}
    >
      <NeuroCard className="h-full min-h-[200px] flex flex-col">
        {/* Card Header */}
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          {/* Drag Handle + Title */}
          <div
            className="flex items-center gap-2 cursor-grab active:cursor-grabbing"
            {...attributes}
            {...listeners}
          >
            <GripVertical className="w-4 h-4 text-muted-foreground/50 hover:text-muted-foreground transition-colors" />
            <span className="text-sm font-semibold text-gunmetal">{widgetDef.name}</span>
          </div>

          {/* Card Menu */}
          <DashboardCardMenu
            onConfigure={handleConfigure}
            onRemove={handleRemove}
          />
        </div>

        {/* Widget Content */}
        <div className="flex-1 pt-3">
          <WidgetComponent
            instanceId={widget.id}
            settings={widget.settings}
          />
        </div>
      </NeuroCard>
    </div>
  );
}
