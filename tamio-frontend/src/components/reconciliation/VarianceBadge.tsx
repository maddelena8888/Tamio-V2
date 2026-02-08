import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface VarianceBadgeProps {
  actual: number | string;
  expected: number | string;
  currency?: string;
  className?: string;
}

function formatCurrency(value: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function VarianceBadge({
  actual,
  expected,
  currency = 'USD',
  className,
}: VarianceBadgeProps) {
  const actualNum = typeof actual === 'string' ? parseFloat(actual) : actual;
  const expectedNum = typeof expected === 'string' ? parseFloat(expected) : expected;

  const variance = actualNum - expectedNum;
  const variancePercent = expectedNum !== 0
    ? Math.round((variance / expectedNum) * 100)
    : 0;

  const isExact = variance === 0;
  const isOver = variance > 0;
  const isUnder = variance < 0;

  let bgColor = 'bg-gray-100';
  let textColor = 'text-gray-600';
  let Icon = Minus;

  if (isOver) {
    bgColor = 'bg-amber-100';
    textColor = 'text-amber-700';
    Icon = TrendingUp;
  } else if (isUnder) {
    bgColor = 'bg-lime/20';
    textColor = 'text-lime-dark';
    Icon = TrendingDown;
  }

  if (isExact) {
    bgColor = 'bg-lime/20';
    textColor = 'text-lime-dark';
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
            bgColor,
            textColor,
            className
          )}
        >
          <Icon className="w-3 h-3" />
          {isExact ? (
            'Exact'
          ) : (
            <>
              {isOver ? '+' : ''}{variancePercent}%
            </>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent>
        <div className="space-y-1 text-sm">
          <p>Expected: {formatCurrency(expectedNum, currency)}</p>
          <p>Actual: {formatCurrency(actualNum, currency)}</p>
          <p>Variance: {variance >= 0 ? '+' : ''}{formatCurrency(variance, currency)}</p>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

export default VarianceBadge;
