import { ChevronDown, ChevronUp } from 'lucide-react';
import { TableRow, TableCell } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { ProjectionRow } from './ProjectionRow';
import type { ProjectionLineItem, ScenarioView, WeeklyAmount } from './types';
import { formatCurrency } from './types';

interface CollapsibleSectionProps {
  title: string;
  items: ProjectionLineItem[];
  totals: WeeklyAmount[];
  type: 'income' | 'cost';
  isExpanded: boolean;
  onToggle: () => void;
  scenarioView: ScenarioView;
  onItemClick: (item: ProjectionLineItem) => void;
  disabledItems?: Set<string>;
  onToggleItem?: (itemId: string) => void;
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

export function CollapsibleSection({
  title,
  items,
  totals,
  type,
  isExpanded,
  onToggle,
  scenarioView,
  onItemClick,
  disabledItems,
  onToggleItem,
}: CollapsibleSectionProps) {
  const isIncome = type === 'income';
  const colorClass = isIncome ? 'text-lime-dark' : 'text-tomato';
  const bgClass = isIncome ? 'bg-lime/5' : 'bg-tomato/5';
  const dotClass = isIncome ? 'bg-lime' : 'bg-tomato';
  const arrowPrefix = isIncome ? '\u2197' : '\u2199'; // ↗ for income, ↙ for costs

  return (
    <>
      {/* Header Row - Always visible, clickable to expand/collapse */}
      <TableRow
        className={cn('cursor-pointer hover:bg-muted/50 transition-colors', bgClass)}
        onClick={onToggle}
      >
        <TableCell className="sticky left-0 z-10 min-w-[200px] bg-inherit">
          <div className="flex items-center gap-2">
            <span className={cn('w-2 h-2 rounded-full', dotClass)} />
            <span className={cn('font-semibold', colorClass)}>
              {arrowPrefix} {title}
            </span>
            <span className="text-xs bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
              {items.length}
            </span>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </div>
        </TableCell>
        {/* Total amounts in header row */}
        {totals.map((amount, i) => {
          const value = getValue(amount, scenarioView);
          return (
            <TableCell
              key={i}
              className={cn('text-center font-semibold min-w-[100px]', colorClass)}
            >
              {formatCurrency(Math.abs(value))}
            </TableCell>
          );
        })}
      </TableRow>

      {/* Individual Items - Only visible when expanded */}
      {isExpanded &&
        items.map((item) => (
          <ProjectionRow
            key={item.id}
            item={item}
            scenarioView={scenarioView}
            onClick={() => onItemClick(item)}
            enabled={!disabledItems?.has(item.name)}
            onToggle={onToggleItem}
          />
        ))}
    </>
  );
}
