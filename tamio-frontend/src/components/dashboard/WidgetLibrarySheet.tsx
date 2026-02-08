/**
 * Widget Library Sheet - Modal for selecting and adding widgets
 *
 * Shows all available widgets organized by category.
 * Already-added widgets are shown as disabled.
 */

import { Check, Plus } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { useDashboard } from '@/contexts/DashboardContext';
import {
  WIDGET_CATEGORIES,
  getWidgetsByCategory,
} from './widgets/registry';
import { cn } from '@/lib/utils';
import type { WidgetId, WidgetDefinition } from './widgets/types';

interface WidgetLibrarySheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function WidgetLibrarySheet({ open, onOpenChange }: WidgetLibrarySheetProps) {
  const { widgets, addWidget } = useDashboard();

  // Get set of already-added widget types
  const addedWidgetIds = new Set(widgets.map((w) => w.widgetId));

  const handleAddWidget = (widgetId: WidgetId) => {
    addWidget(widgetId);
    // Optionally close sheet after adding
    // onOpenChange(false);
  };

  // Get implemented widgets by category
  const categories = Object.entries(WIDGET_CATEGORIES)
    .map(([key, category]) => ({
      key,
      ...category,
      widgets: getWidgetsByCategory(key),
    }))
    .filter((cat) => cat.widgets.length > 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Add Card</SheetTitle>
          <SheetDescription>
            Choose a card to add to your dashboard. Click to add.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {categories.map((category) => (
            <div key={category.key}>
              {/* Category Header */}
              <div className="mb-3">
                <h3 className="text-sm font-semibold text-gunmetal">{category.label}</h3>
                <p className="text-xs text-muted-foreground">{category.description}</p>
              </div>

              {/* Widget List */}
              <div className="space-y-2">
                {category.widgets.map((widget) => (
                  <WidgetItem
                    key={widget.id}
                    widget={widget}
                    isAdded={addedWidgetIds.has(widget.id)}
                    onAdd={() => handleAddWidget(widget.id)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ============================================================================
// Widget Item Component
// ============================================================================

interface WidgetItemProps {
  widget: WidgetDefinition;
  isAdded: boolean;
  onAdd: () => void;
}

function WidgetItem({ widget, isAdded, onAdd }: WidgetItemProps) {
  const Icon = widget.icon;

  return (
    <div
      className={cn(
        'flex items-center gap-3 p-3 rounded-lg border transition-colors',
        isAdded
          ? 'bg-gray-50 border-gray-200 opacity-60'
          : 'bg-white/60 border-white/30 hover:bg-white/80 hover:border-gray-200'
      )}
    >
      {/* Icon */}
      <div
        className={cn(
          'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
          isAdded ? 'bg-gray-100' : 'bg-gunmetal/5'
        )}
      >
        <Icon className={cn('w-5 h-5', isAdded ? 'text-gray-400' : 'text-gunmetal')} />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <h4
          className={cn(
            'text-sm font-medium',
            isAdded ? 'text-gray-500' : 'text-gunmetal'
          )}
        >
          {widget.name}
        </h4>
        <p className="text-xs text-muted-foreground line-clamp-1">
          {widget.description}
        </p>
      </div>

      {/* Action */}
      {isAdded ? (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Check className="w-4 h-4" />
          Added
        </div>
      ) : (
        <Button
          size="sm"
          variant="ghost"
          onClick={onAdd}
          className="flex-shrink-0"
        >
          <Plus className="w-4 h-4 mr-1" />
          Add
        </Button>
      )}
    </div>
  );
}
