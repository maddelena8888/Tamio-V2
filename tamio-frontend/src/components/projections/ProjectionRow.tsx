import { TableRow, TableCell } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import type { ProjectionLineItem, ScenarioView, WeeklyAmount } from './types';
import { formatCurrency } from './types';

interface ProjectionRowProps {
  item: ProjectionLineItem;
  scenarioView: ScenarioView;
  onClick: () => void;
  enabled?: boolean;
  onToggle?: (itemId: string) => void;
}

function getValue(amount: WeeklyAmount, scenarioView: ScenarioView): number {
  switch (scenarioView) {
    case 'bestCase':
      return amount.bestCase;
    case 'worstCase':
      return amount.worstCase;
    default:
      return amount.expected;
  }
}

export function ProjectionRow({ item, scenarioView, onClick, enabled = true, onToggle }: ProjectionRowProps) {
  const isIncome = item.type === 'income';
  const colorClass = isIncome ? 'text-lime-dark' : 'text-tomato';
  const prefix = isIncome ? '+ ' : '- ';

  const handleToggleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  return (
    <TableRow
      className={cn(
        'cursor-pointer hover:bg-muted/30 transition-colors',
        !enabled && 'opacity-50'
      )}
      onClick={onClick}
    >
      <TableCell className="sticky left-0 bg-white z-10 pl-4 min-w-[200px]">
        <div className="flex items-center gap-2">
          {onToggle && (
            <div onClick={handleToggleClick}>
              <Switch
                checked={enabled}
                onCheckedChange={() => onToggle(item.name)}
                className={cn(
                  'scale-75',
                  isIncome ? 'data-[state=checked]:bg-lime-dark' : 'data-[state=checked]:bg-tomato'
                )}
              />
            </div>
          )}
          <span className={cn('text-sm', colorClass)}>{prefix}</span>
          <span className={cn('truncate text-sm', !enabled && 'line-through')}>{item.name}</span>
          {/* Confidence indicator */}
          <span
            className={cn(
              'w-1.5 h-1.5 rounded-full flex-shrink-0',
              item.confidence === 'high'
                ? 'bg-lime-dark'
                : item.confidence === 'medium'
                  ? 'bg-amber-500'
                  : 'bg-tomato'
            )}
            title={`${item.confidence} confidence`}
          />
        </div>
      </TableCell>
      {item.weeklyAmounts.map((amount, i) => {
        const value = getValue(amount, scenarioView);
        return (
          <TableCell
            key={i}
            className={cn('text-center text-sm min-w-[100px]', colorClass)}
          >
            {value !== 0 ? formatCurrency(Math.abs(value)) : '$0'}
          </TableCell>
        );
      })}
    </TableRow>
  );
}
