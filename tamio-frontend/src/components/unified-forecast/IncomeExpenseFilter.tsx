import { Check, TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUnifiedForecastContext, useAllCategoriesToggle } from './UnifiedForecastContext';

// ============================================================================
// FilterChip Component
// ============================================================================

interface FilterChipProps {
  label: string;
  isActive: boolean;
  type: 'income' | 'cost' | 'master';
  onClick: () => void;
}

function FilterChip({ label, isActive, type, onClick }: FilterChipProps) {
  const baseClasses =
    'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all cursor-pointer select-none';

  const activeClasses = {
    income: 'bg-lime/20 text-lime-dark border border-lime/40',
    cost: 'bg-tomato/20 text-tomato border border-tomato/40',
    master: 'bg-gunmetal text-white border border-gunmetal',
  };

  const inactiveClasses =
    'bg-white/60 text-muted-foreground border border-gray-200 hover:bg-white/80';

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(baseClasses, isActive ? activeClasses[type] : inactiveClasses)}
    >
      {isActive && <Check className="h-3.5 w-3.5" />}
      {label}
    </button>
  );
}

// ============================================================================
// IncomeExpenseFilter Component
// ============================================================================

interface IncomeExpenseFilterProps {
  className?: string;
  showIndividualFilters?: boolean;
}

export function IncomeExpenseFilter({
  className,
  showIndividualFilters = true,
}: IncomeExpenseFilterProps) {
  const { categoryFilters, toggleCategory, toggleAllCategories } = useUnifiedForecastContext();
  const { allIncomeVisible, allCostsVisible } = useAllCategoriesToggle();

  const incomeFilters = categoryFilters.filter(f => f.type === 'income');
  const costFilters = categoryFilters.filter(f => f.type === 'cost');

  return (
    <div className={cn('space-y-3', className)}>
      {/* Master Toggles */}
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium text-muted-foreground">Filter by:</span>

        <div className="flex items-center gap-2">
          <FilterChip
            label="All Income"
            isActive={allIncomeVisible}
            type="income"
            onClick={() => toggleAllCategories('income', !allIncomeVisible)}
          />
          <FilterChip
            label="All Costs"
            isActive={allCostsVisible}
            type="cost"
            onClick={() => toggleAllCategories('cost', !allCostsVisible)}
          />
        </div>
      </div>

      {/* Individual Category Filters */}
      {showIndividualFilters && (incomeFilters.length > 0 || costFilters.length > 0) && (
        <div className="flex flex-wrap gap-2">
          {/* Income Categories */}
          {incomeFilters.length > 0 && (
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-lime-dark" />
              {incomeFilters.map(filter => (
                <FilterChip
                  key={filter.id}
                  label={filter.name}
                  isActive={filter.visible}
                  type="income"
                  onClick={() => toggleCategory(filter.id)}
                />
              ))}
            </div>
          )}

          {/* Separator */}
          {incomeFilters.length > 0 && costFilters.length > 0 && (
            <div className="h-6 w-px bg-gray-200 mx-2" />
          )}

          {/* Cost Categories */}
          {costFilters.length > 0 && (
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-tomato" />
              {costFilters.map(filter => (
                <FilterChip
                  key={filter.id}
                  label={filter.name}
                  isActive={filter.visible}
                  type="cost"
                  onClick={() => toggleCategory(filter.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
