/**
 * AlertsPanelSection Component
 *
 * Main container for the dashboard alerts panel.
 * Displays summary bar and horizontally scrollable alert cards.
 */

import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  NeuroCard,
  NeuroCardContent,
  NeuroCardHeader,
  NeuroCardTitle,
} from '@/components/ui/neuro-card';
import { AlertsPanelSummaryBar } from './AlertsPanelSummaryBar';
import { AlertsPanelCard } from './AlertsPanelCard';
import { AlertImpactModal } from './AlertImpactModal';
import { useAlertsPanelData } from './useAlertsPanelData';
import type { AlertPanelItem } from './types';

interface AlertsPanelSectionProps {
  className?: string;
  onAlertClick?: (alertId: string) => void;
}

/**
 * Loading skeleton for alert cards
 */
function AlertCardSkeleton() {
  return (
    <div className="w-[340px] h-[160px] flex-shrink-0 rounded-2xl bg-gradient-to-br from-gray-100/80 to-gray-50/60 backdrop-blur-xl animate-pulse" />
  );
}

/**
 * Empty state when no alerts
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="w-12 h-12 rounded-full bg-lime/10 flex items-center justify-center mb-3">
        <AlertCircle className="w-6 h-6 text-lime" />
      </div>
      <h4 className="font-medium text-gunmetal mb-1">All Clear</h4>
      <p className="text-sm text-gray-500">No alerts requiring attention right now</p>
    </div>
  );
}

export function AlertsPanelSection({ className, onAlertClick }: AlertsPanelSectionProps) {
  const navigate = useNavigate();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  // Modal state for alert impact popup
  const [selectedItem, setSelectedItem] = useState<AlertPanelItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const {
    items,
    summary,
    isLoading,
    error,
    refetch,
  } = useAlertsPanelData();

  // Handle scroll state for showing/hiding navigation arrows
  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
    setCanScrollLeft(scrollLeft > 0);
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
  };

  // Scroll by one card width
  const scroll = (direction: 'left' | 'right') => {
    if (!scrollContainerRef.current) return;
    const scrollAmount = 360; // Slightly more than card width (340px + gap)
    scrollContainerRef.current.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    });
  };

  // Navigate to full alerts page
  const handleViewAll = () => {
    navigate('/health');
  };

  // Handle alert card click - open impact modal
  const handleCardClick = (item: AlertPanelItem) => {
    if (onAlertClick) {
      onAlertClick(item.alert.id);
    } else {
      setSelectedItem(item);
      setModalOpen(true);
    }
  };

  // Error state
  if (error) {
    return (
      <NeuroCard className={className}>
        <NeuroCardContent className="py-8">
          <div className="text-center text-gray-500">
            <p>Failed to load alerts</p>
            <Button variant="ghost" size="sm" onClick={refetch} className="mt-2">
              Try again
            </Button>
          </div>
        </NeuroCardContent>
      </NeuroCard>
    );
  }

  return (
    <NeuroCard className={className}>
      <NeuroCardHeader className="pb-2">
        <NeuroCardTitle>Alerts</NeuroCardTitle>
      </NeuroCardHeader>

      <NeuroCardContent className="pt-0">
        {/* Summary Bar */}
        <AlertsPanelSummaryBar
          summary={summary}
          isLoading={isLoading}
          onRefresh={refetch}
          onViewAll={handleViewAll}
        />

        {/* Cards Container */}
        {isLoading ? (
          <div className="flex gap-4 py-4">
            <AlertCardSkeleton />
            <AlertCardSkeleton />
            <AlertCardSkeleton />
          </div>
        ) : items.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="relative py-4">
            {/* Scroll Left Button */}
            {canScrollLeft && (
              <button
                onClick={() => scroll('left')}
                className={cn(
                  'absolute left-0 top-1/2 -translate-y-1/2 z-10',
                  'w-8 h-8 rounded-full bg-white shadow-lg border border-gray-200',
                  'flex items-center justify-center',
                  'hover:bg-gray-50 transition-colors'
                )}
              >
                <ChevronLeft className="w-5 h-5 text-gray-600" />
              </button>
            )}

            {/* Scrollable Cards */}
            <div
              ref={scrollContainerRef}
              onScroll={handleScroll}
              className={cn(
                'flex gap-4 overflow-x-auto pb-2',
                'snap-x snap-mandatory scroll-smooth',
                'scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent',
                // Add padding for scroll buttons
                canScrollLeft && 'pl-6',
                canScrollRight && 'pr-6'
              )}
            >
              {items.map((item) => (
                <div key={item.id} className="snap-start">
                  <AlertsPanelCard
                    item={item}
                    onClick={handleCardClick}
                  />
                </div>
              ))}
            </div>

            {/* Scroll Right Button */}
            {canScrollRight && items.length > 3 && (
              <button
                onClick={() => scroll('right')}
                className={cn(
                  'absolute right-0 top-1/2 -translate-y-1/2 z-10',
                  'w-8 h-8 rounded-full bg-white shadow-lg border border-gray-200',
                  'flex items-center justify-center',
                  'hover:bg-gray-50 transition-colors'
                )}
              >
                <ChevronRight className="w-5 h-5 text-gray-600" />
              </button>
            )}
          </div>
        )}
      </NeuroCardContent>

      {/* Alert Impact Modal */}
      <AlertImpactModal
        item={selectedItem}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </NeuroCard>
  );
}
