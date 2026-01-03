import * as React from 'react';
import { cn } from '@/lib/utils';

export type NeuroCardProps = React.HTMLAttributes<HTMLDivElement>

const NeuroCard = React.forwardRef<HTMLDivElement, NeuroCardProps>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'rounded-2xl bg-white/40 backdrop-blur-md p-6',
          'border border-white/20',
          'shadow-lg shadow-black/5',
          'transition-all duration-300',
          className
        )}
        {...props}
      />
    );
  }
);
NeuroCard.displayName = 'NeuroCard';

const NeuroCardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('flex flex-col space-y-1.5 pb-4', className)}
    {...props}
  />
));
NeuroCardHeader.displayName = 'NeuroCardHeader';

const NeuroCardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn('text-lg font-semibold leading-none tracking-tight', className)}
    {...props}
  />
));
NeuroCardTitle.displayName = 'NeuroCardTitle';

const NeuroCardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn('text-sm text-muted-foreground', className)}
    {...props}
  />
));
NeuroCardDescription.displayName = 'NeuroCardDescription';

const NeuroCardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('', className)} {...props} />
));
NeuroCardContent.displayName = 'NeuroCardContent';

export { NeuroCard, NeuroCardHeader, NeuroCardTitle, NeuroCardDescription, NeuroCardContent };
