/**
 * Widget Skeleton - Loading state for dashboard widgets
 */

import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface WidgetSkeletonProps {
  className?: string;
  /** Show a compact skeleton for smaller widgets */
  compact?: boolean;
}

export function WidgetSkeleton({ className, compact = false }: WidgetSkeletonProps) {
  if (compact) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-2 py-4', className)}>
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-4 w-32" />
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {/* Hero metric skeleton */}
      <div className="flex-1 flex items-center justify-center py-6">
        <Skeleton className="h-12 w-32" />
      </div>
      {/* Sublabel skeleton */}
      <div className="flex justify-center">
        <Skeleton className="h-4 w-40" />
      </div>
      {/* Optional action link skeleton */}
      <div className="flex justify-center pt-2">
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  );
}
