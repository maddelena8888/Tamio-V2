import type { Confidence, ForecastResponse, ForecastWeek, ForecastEventSummary } from '@/lib/api/types';

// Scenario view type for toggling between expected, best, and worst case
export type ScenarioView = 'expected' | 'bestCase' | 'worstCase';

// Weekly amount with scenario variants
export interface WeeklyAmount {
  weekNumber: number;
  expected: number;
  bestCase: number;
  worstCase: number;
}

// Individual line item (income or cost)
export interface ProjectionLineItem {
  id: string;
  name: string;
  type: 'income' | 'cost';
  category: string | null;
  confidence: Confidence;
  confidenceReason?: string;
  sourceType?: string;
  weeklyAmounts: WeeklyAmount[];
}

// Transformed table data structure
export interface ProjectionsTableData {
  weekNumbers: number[];
  startingBalance: WeeklyAmount[];
  incomeItems: ProjectionLineItem[];
  totalIncome: WeeklyAmount[];
  costItems: ProjectionLineItem[];
  totalCosts: WeeklyAmount[];
  endingBalance: WeeklyAmount[];
}

// Currency formatter
export const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

// Calculate best/worst case based on expected value and week index
function calculateScenarioValues(
  expected: number,
  weekIndex: number
): { bestCase: number; worstCase: number } {
  // Uncertainty grows 2% per week
  const uncertaintyFactor = 1 + weekIndex * 0.02;
  // Base 15% variance
  const variance = Math.abs(expected) * 0.15 * uncertaintyFactor;

  return {
    bestCase: expected + variance,
    worstCase: Math.max(0, expected - variance),
  };
}

// Transform forecast API response to projections table data
export function transformForecastToProjections(
  forecast: ForecastResponse,
  maxWeeks: number = 9
): ProjectionsTableData {
  const weeks = forecast.weeks.slice(0, maxWeeks);
  const weekNumbers = weeks.map((_, i) => i);

  // Group events by source_name or category
  const incomeMap = new Map<string, { items: ForecastEventSummary[]; weekAmounts: Map<number, number> }>();
  const costMap = new Map<string, { items: ForecastEventSummary[]; weekAmounts: Map<number, number> }>();

  weeks.forEach((week, weekIndex) => {
    week.events.forEach((event) => {
      const name = event.source_name || event.category || 'Other';
      const amount = parseFloat(event.amount);
      const map = event.direction === 'in' ? incomeMap : costMap;

      if (!map.has(name)) {
        map.set(name, { items: [], weekAmounts: new Map() });
      }

      const entry = map.get(name)!;
      entry.items.push(event);
      const currentAmount = entry.weekAmounts.get(weekIndex) || 0;
      entry.weekAmounts.set(weekIndex, currentAmount + amount);
    });
  });

  // Convert maps to ProjectionLineItem arrays
  const createLineItems = (
    map: Map<string, { items: ForecastEventSummary[]; weekAmounts: Map<number, number> }>,
    type: 'income' | 'cost'
  ): ProjectionLineItem[] => {
    return Array.from(map.entries()).map(([name, data]) => {
      // Use the first event's metadata for confidence, category, etc.
      const firstEvent = data.items[0];

      const weeklyAmounts: WeeklyAmount[] = weekNumbers.map((weekIndex) => {
        const expected = data.weekAmounts.get(weekIndex) || 0;
        const { bestCase, worstCase } = calculateScenarioValues(expected, weekIndex);
        return { weekNumber: weekIndex, expected, bestCase, worstCase };
      });

      return {
        id: firstEvent?.id || name,
        name,
        type,
        category: firstEvent?.category || null,
        confidence: firstEvent?.confidence || 'medium',
        confidenceReason: firstEvent?.confidence_reason,
        sourceType: firstEvent?.source_type,
        weeklyAmounts,
      };
    });
  };

  const incomeItems = createLineItems(incomeMap, 'income');
  const costItems = createLineItems(costMap, 'cost');

  // Calculate totals and balances
  const startingBalance: WeeklyAmount[] = weeks.map((week, weekIndex) => {
    const expected = parseFloat(week.starting_balance);
    const { bestCase, worstCase } = calculateScenarioValues(expected, weekIndex);
    return { weekNumber: weekIndex, expected, bestCase, worstCase };
  });

  const totalIncome: WeeklyAmount[] = weeks.map((week, weekIndex) => {
    const expected = parseFloat(week.cash_in);
    const { bestCase, worstCase } = calculateScenarioValues(expected, weekIndex);
    return { weekNumber: weekIndex, expected, bestCase, worstCase };
  });

  const totalCosts: WeeklyAmount[] = weeks.map((week, weekIndex) => {
    const expected = parseFloat(week.cash_out);
    const { bestCase, worstCase } = calculateScenarioValues(expected, weekIndex);
    return { weekNumber: weekIndex, expected, bestCase, worstCase };
  });

  const endingBalance: WeeklyAmount[] = weeks.map((week, weekIndex) => {
    const expected = parseFloat(week.ending_balance);
    const { bestCase, worstCase } = calculateScenarioValues(expected, weekIndex);
    return { weekNumber: weekIndex, expected, bestCase, worstCase };
  });

  return {
    weekNumbers,
    startingBalance,
    incomeItems,
    totalIncome,
    costItems,
    totalCosts,
    endingBalance,
  };
}
