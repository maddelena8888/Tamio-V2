import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface AIConfidenceIndicatorProps {
  confidence: number; // 0.0 - 1.0
  className?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'bg-lime';
  if (confidence >= 0.5) return 'bg-amber-400';
  return 'bg-tomato';
}

function getConfidenceLabel(confidence: number): string {
  if (confidence >= 0.95) return 'Very High';
  if (confidence >= 0.8) return 'High';
  if (confidence >= 0.7) return 'Medium';
  if (confidence >= 0.5) return 'Low';
  return 'Very Low';
}

export function AIConfidenceIndicator({
  confidence,
  className,
  showLabel = false,
  size = 'sm',
}: AIConfidenceIndicatorProps) {
  const percentage = Math.round(confidence * 100);
  const colorClass = getConfidenceColor(confidence);
  const label = getConfidenceLabel(confidence);

  const dotSizes = {
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
    lg: 'w-3 h-3',
  };

  const textSizes = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className={cn('flex items-center gap-1.5', className)}>
          <div className={cn('rounded-full', colorClass, dotSizes[size])} />
          <span className={cn('text-muted-foreground', textSizes[size])}>
            {percentage}%
          </span>
          {showLabel && (
            <span className={cn('text-muted-foreground', textSizes[size])}>
              ({label})
            </span>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent>
        <p>AI Confidence: {percentage}% ({label})</p>
      </TooltipContent>
    </Tooltip>
  );
}

export default AIConfidenceIndicator;
