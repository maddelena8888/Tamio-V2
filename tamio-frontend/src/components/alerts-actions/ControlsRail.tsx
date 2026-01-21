/**
 * ControlsRail Component - V4 Risk/Controls Architecture
 *
 * Horizontal scrollable rail showing active controls.
 * Replaces the Kanban board with a more "system state" visualization.
 */

import { useRef, useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ControlPill, EmptyControlsState } from './ControlPill';
import type { Control } from '@/lib/api/alertsActions';

interface ControlsRailProps {
  controls: Control[];
  selectedControlId: string | null;
  highlightedControlIds: Set<string>;
  controlRiskMap: Map<string, string[]>;
  getRiskById: (id: string) => { title: string } | undefined;
  onControlClick: (control: Control) => void;
}

export function ControlsRail({
  controls,
  selectedControlId,
  highlightedControlIds,
  controlRiskMap,
  getRiskById,
  onControlClick,
}: ControlsRailProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Group controls by state for visual organization
  const groupedControls = {
    active: controls.filter((c) => c.state === 'active'),
    pending: controls.filter((c) => c.state === 'pending'),
    needs_review: controls.filter((c) => c.state === 'needs_review'),
    completed: controls.filter((c) => c.state === 'completed'),
  };

  // Flatten with priority: active -> pending -> needs_review -> completed
  const sortedControls = [
    ...groupedControls.active,
    ...groupedControls.pending,
    ...groupedControls.needs_review,
    ...groupedControls.completed,
  ];

  // Check scroll state
  const updateScrollButtons = () => {
    if (scrollContainerRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 1);
    }
  };

  useEffect(() => {
    updateScrollButtons();
    window.addEventListener('resize', updateScrollButtons);
    return () => window.removeEventListener('resize', updateScrollButtons);
  }, [controls]);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const scrollAmount = 300;
      scrollContainerRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };

  if (sortedControls.length === 0) {
    return (
      <div className="bg-white/60 backdrop-blur-md rounded-xl border border-white/40 shadow-sm">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100/50">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-gray-400" />
            <h3 className="text-sm font-semibold text-gunmetal">Active Actions</h3>
          </div>
        </div>
        <EmptyControlsState />
      </div>
    );
  }

  return (
    <div className="bg-white/60 backdrop-blur-md rounded-xl border border-white/40 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100/50">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-gray-400" />
          <h3 className="text-sm font-semibold text-gunmetal">Active Actions</h3>
          <span className="text-xs text-gray-500">
            ({sortedControls.length})
          </span>
        </div>

        {/* State summary */}
        <div className="flex items-center gap-3 text-xs text-gray-500">
          {groupedControls.active.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              {groupedControls.active.length} in progress
            </span>
          )}
          {groupedControls.pending.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-gray-400" />
              {groupedControls.pending.length} pending
            </span>
          )}
          {groupedControls.needs_review.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              {groupedControls.needs_review.length} need review
            </span>
          )}
        </div>
      </div>

      {/* Rail */}
      <div className="relative">
        {/* Scroll shadow left */}
        {canScrollLeft && (
          <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-white/60 to-transparent z-10 pointer-events-none" />
        )}

        {/* Scroll shadow right */}
        {canScrollRight && (
          <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-white/60 to-transparent z-10 pointer-events-none" />
        )}

        {/* Scroll button left */}
        {canScrollLeft && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => scroll('left')}
            className="absolute left-1 top-1/2 -translate-y-1/2 z-20 h-8 w-8 p-0 rounded-full bg-white shadow-md border border-gray-200"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
        )}

        {/* Scroll button right */}
        {canScrollRight && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => scroll('right')}
            className="absolute right-1 top-1/2 -translate-y-1/2 z-20 h-8 w-8 p-0 rounded-full bg-white shadow-md border border-gray-200"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        )}

        {/* Scrollable container */}
        <div
          ref={scrollContainerRef}
          onScroll={updateScrollButtons}
          className="flex items-center gap-2 px-4 py-3 overflow-x-auto scrollbar-hide"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {sortedControls.map((control) => {
            const linkedRiskIds = controlRiskMap.get(control.id) || [];
            const linkedRisk = linkedRiskIds.length > 0 ? getRiskById(linkedRiskIds[0]) : undefined;
            return (
              <ControlPill
                key={control.id}
                control={control}
                isHighlighted={highlightedControlIds.has(control.id)}
                isSelected={selectedControlId === control.id}
                linkedRiskCount={linkedRiskIds.length}
                linkedRiskName={linkedRisk?.title}
                onClick={() => onControlClick(control)}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
