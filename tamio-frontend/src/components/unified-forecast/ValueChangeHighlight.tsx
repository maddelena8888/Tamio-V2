import { useRef, useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/components/projections/types';

// ============================================================================
// Hook: usePrevious
// ============================================================================

function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T | undefined>(undefined);
  useEffect(() => {
    ref.current = value;
  }, [value]);
  return ref.current;
}

// ============================================================================
// ValueChangeHighlight Component
// ============================================================================

interface ValueChangeHighlightProps {
  value: number;
  className?: string;
  formatFn?: (value: number) => string;
  /** Duration of the highlight animation in ms */
  duration?: number;
  /** Show + prefix for positive values */
  showSign?: boolean;
  /** Invert colors (red for increase, green for decrease) - useful for costs */
  invertColors?: boolean;
}

export function ValueChangeHighlight({
  value,
  className,
  formatFn = formatCurrency,
  duration = 600,
  showSign = false,
  invertColors = false,
}: ValueChangeHighlightProps) {
  const previousValue = usePrevious(value);
  const [animationKey, setAnimationKey] = useState(0);
  const [changeDirection, setChangeDirection] = useState<'up' | 'down' | null>(null);

  // Detect changes and trigger animation
  useEffect(() => {
    if (previousValue !== undefined && previousValue !== value) {
      const direction = value > previousValue ? 'up' : 'down';
      setChangeDirection(direction);
      setAnimationKey(k => k + 1);

      // Clear highlight after animation
      const timer = setTimeout(() => {
        setChangeDirection(null);
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [value, previousValue, duration]);

  // Determine highlight color
  const getHighlightClass = () => {
    if (!changeDirection) return '';

    const isPositive = invertColors
      ? changeDirection === 'down' // For costs, decrease is good
      : changeDirection === 'up'; // For income, increase is good

    return isPositive ? 'text-lime-dark bg-lime/10' : 'text-tomato bg-tomato/10';
  };

  // Format the display value
  const formattedValue = formatFn(value);
  const displayValue = showSign && value > 0 ? `+${formattedValue}` : formattedValue;

  return (
    <span
      key={animationKey}
      className={cn(
        'transition-all rounded px-1 -mx-1',
        changeDirection && 'animate-highlight',
        getHighlightClass(),
        className
      )}
      style={{
        animationDuration: `${duration}ms`,
      }}
    >
      {displayValue}
    </span>
  );
}

// ============================================================================
// Delta Display Component (shows change amount)
// ============================================================================

interface DeltaDisplayProps {
  currentValue: number;
  baseValue: number;
  className?: string;
  formatFn?: (value: number) => string;
}

export function DeltaDisplay({
  currentValue,
  baseValue,
  className,
  formatFn = formatCurrency,
}: DeltaDisplayProps) {
  const delta = currentValue - baseValue;

  if (delta === 0) return null;

  const isPositive = delta > 0;
  const displayValue = formatFn(Math.abs(delta));

  return (
    <span
      className={cn(
        'text-xs font-medium ml-1',
        isPositive ? 'text-lime-dark' : 'text-tomato',
        className
      )}
    >
      {isPositive ? '+' : '-'}
      {displayValue}
    </span>
  );
}

// ============================================================================
// Percentage Change Display
// ============================================================================

interface PercentageChangeProps {
  currentValue: number;
  baseValue: number;
  className?: string;
}

export function PercentageChange({ currentValue, baseValue, className }: PercentageChangeProps) {
  if (baseValue === 0) return null;

  const percentChange = ((currentValue - baseValue) / Math.abs(baseValue)) * 100;

  if (Math.abs(percentChange) < 0.1) return null;

  const isPositive = percentChange > 0;
  const displayValue = Math.abs(percentChange).toFixed(1);

  return (
    <span
      className={cn(
        'text-xs font-medium',
        isPositive ? 'text-lime-dark' : 'text-tomato',
        className
      )}
    >
      {isPositive ? '+' : '-'}
      {displayValue}%
    </span>
  );
}

// ============================================================================
// CSS for animation (add to index.css or component styles)
// ============================================================================

// Add this to your global CSS or create a style tag:
/*
@keyframes highlight {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
  100% {
    opacity: 1;
    background-color: transparent;
  }
}

.animate-highlight {
  animation: highlight ease-out;
}
*/
