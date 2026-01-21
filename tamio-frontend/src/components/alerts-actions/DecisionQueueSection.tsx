/**
 * DecisionQueueSection Component
 *
 * A collapsible section wrapper for the Decision Queue page.
 * Displays a header with icon, title, count badge, and chevron indicator.
 * Uses Radix Collapsible for smooth expand/collapse animation.
 */

import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { NeuroCard } from '@/components/ui/neuro-card';

type DotColor = 'red' | 'blue' | 'green';

interface DecisionQueueSectionProps {
  title: string;
  dotColor: DotColor;
  count: number;
  defaultOpen?: boolean;
  children: ReactNode;
  emptyMessage?: string;
}

const dotColorClasses: Record<DotColor, string> = {
  red: 'bg-tomato',
  blue: 'bg-blue-500',
  green: 'bg-lime',
};

export function DecisionQueueSection({
  title,
  dotColor,
  count,
  defaultOpen = false,
  children,
  emptyMessage = 'No items in this section',
}: DecisionQueueSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <NeuroCard className="p-0 overflow-hidden">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <button
            className={cn(
              'w-full flex items-center justify-between p-4',
              'hover:bg-gray-50/50 transition-colors duration-150',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-gunmetal/20 focus-visible:ring-inset'
            )}
          >
            <div className="flex items-center gap-3">
              {/* Colored dot indicator */}
              <span
                className={cn(
                  'w-3 h-3 rounded-full flex-shrink-0',
                  dotColorClasses[dotColor]
                )}
              />

              {/* Section title */}
              <span className="font-semibold text-gunmetal">{title}</span>

              {/* Count badge */}
              <span
                className={cn(
                  'px-2 py-0.5 rounded-full text-xs font-medium',
                  'bg-gray-100 text-gray-600'
                )}
              >
                {count}
              </span>
            </div>

            {/* Chevron indicator */}
            <ChevronDown
              className={cn(
                'w-5 h-5 text-gray-400 transition-transform duration-200',
                isOpen && 'rotate-180'
              )}
            />
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="border-t border-gray-100">
            {count === 0 ? (
              <div className="flex items-center justify-center py-8 text-gray-500 text-sm">
                {emptyMessage}
              </div>
            ) : (
              <div className="p-4 space-y-4">{children}</div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </NeuroCard>
  );
}
