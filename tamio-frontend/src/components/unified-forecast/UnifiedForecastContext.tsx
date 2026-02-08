import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useRef,
  type ReactNode,
} from 'react';
import type {
  ForecastResponse,
  Scenario,
  ScenarioSuggestion,
  ScenarioComparisonResponse,
} from '@/lib/api/types';
import type { ScenarioView, ProjectionsTableData } from '@/components/projections/types';

// ============================================================================
// Types
// ============================================================================

export type TimeRange = '13' | '26' | '52';
export type Granularity = 'monthly' | 'weekly';

export interface CategoryFilter {
  id: string;
  name: string;
  type: 'income' | 'cost';
  visible: boolean;
}

export interface AppliedScenario {
  id: string;
  name: string;
  color: string;
  comparison: ScenarioComparisonResponse;
  tableData: ProjectionsTableData;
}

interface UnifiedForecastState {
  // Data
  forecast: ForecastResponse | null;
  scenarios: Scenario[];
  suggestions: ScenarioSuggestion[];

  // View state
  timeRange: TimeRange;
  scenarioView: ScenarioView;
  granularity: Granularity;
  categoryFilters: CategoryFilter[];

  // Applied scenarios (with cached data)
  appliedScenarios: AppliedScenario[];

  // UI state
  isLoading: boolean;
  isScenarioLoading: boolean;
  isPanelCollapsed: boolean;
  error: string | null;
}

interface UnifiedForecastActions {
  // Data actions
  setForecast: (forecast: ForecastResponse | null) => void;
  setScenarios: (scenarios: Scenario[]) => void;
  setSuggestions: (suggestions: ScenarioSuggestion[]) => void;

  // View actions
  setTimeRange: (range: TimeRange) => void;
  setScenarioView: (view: ScenarioView) => void;
  setGranularity: (granularity: Granularity) => void;
  toggleCategory: (categoryId: string) => void;
  toggleAllCategories: (type: 'income' | 'cost', visible: boolean) => void;
  setCategoryFilters: (filters: CategoryFilter[]) => void;

  // Scenario actions
  applyScenario: (scenario: AppliedScenario) => void;
  removeScenario: (scenarioId: string) => void;
  clearAllScenarios: () => void;

  // UI actions
  setIsLoading: (loading: boolean) => void;
  setIsScenarioLoading: (loading: boolean) => void;
  togglePanel: () => void;
  setError: (error: string | null) => void;
}

type UnifiedForecastContextType = UnifiedForecastState & UnifiedForecastActions;

// ============================================================================
// Scenario Colors
// ============================================================================

export const SCENARIO_COLORS = [
  '#C5FF35', // lime
  '#8B5CF6', // purple
  '#F59E0B', // amber
  '#06B6D4', // cyan
  '#EC4899', // pink
];

export function getScenarioColor(index: number): string {
  return SCENARIO_COLORS[index % SCENARIO_COLORS.length];
}

// ============================================================================
// Context
// ============================================================================

const UnifiedForecastContext = createContext<UnifiedForecastContextType | undefined>(undefined);

export function UnifiedForecastProvider({ children }: { children: ReactNode }) {
  // Data state
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [suggestions, setSuggestions] = useState<ScenarioSuggestion[]>([]);

  // View state
  const [timeRange, setTimeRange] = useState<TimeRange>('13');
  const [scenarioView, setScenarioView] = useState<ScenarioView>('expected');
  const [granularity, setGranularity] = useState<Granularity>('weekly');
  const [categoryFilters, setCategoryFilters] = useState<CategoryFilter[]>([]);

  // Applied scenarios
  const [appliedScenarios, setAppliedScenarios] = useState<AppliedScenario[]>([]);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [isScenarioLoading, setIsScenarioLoading] = useState(false);
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Scenario comparison cache (for performance)
  const scenarioCache = useRef<Map<string, ScenarioComparisonResponse>>(new Map());

  // Category toggle handlers
  const toggleCategory = useCallback((categoryId: string) => {
    setCategoryFilters(prev =>
      prev.map(filter =>
        filter.id === categoryId ? { ...filter, visible: !filter.visible } : filter
      )
    );
  }, []);

  const toggleAllCategories = useCallback((type: 'income' | 'cost', visible: boolean) => {
    setCategoryFilters(prev =>
      prev.map(filter =>
        filter.type === type ? { ...filter, visible } : filter
      )
    );
  }, []);

  // Scenario handlers
  const applyScenario = useCallback((scenario: AppliedScenario) => {
    setAppliedScenarios(prev => {
      // Check if already applied
      if (prev.some(s => s.id === scenario.id)) {
        return prev;
      }
      // Limit to 5 scenarios
      if (prev.length >= 5) {
        return prev;
      }
      // Assign color based on current count
      const coloredScenario = {
        ...scenario,
        color: getScenarioColor(prev.length),
      };
      // Cache the comparison
      scenarioCache.current.set(scenario.id, scenario.comparison);
      return [...prev, coloredScenario];
    });
  }, []);

  const removeScenario = useCallback((scenarioId: string) => {
    setAppliedScenarios(prev => {
      const filtered = prev.filter(s => s.id !== scenarioId);
      // Reassign colors to maintain consistency
      return filtered.map((s, i) => ({ ...s, color: getScenarioColor(i) }));
    });
  }, []);

  const clearAllScenarios = useCallback(() => {
    setAppliedScenarios([]);
    scenarioCache.current.clear();
  }, []);

  // Panel toggle
  const togglePanel = useCallback(() => {
    setIsPanelCollapsed(prev => !prev);
  }, []);

  const value = useMemo<UnifiedForecastContextType>(
    () => ({
      // State
      forecast,
      scenarios,
      suggestions,
      timeRange,
      scenarioView,
      granularity,
      categoryFilters,
      appliedScenarios,
      isLoading,
      isScenarioLoading,
      isPanelCollapsed,
      error,

      // Actions
      setForecast,
      setScenarios,
      setSuggestions,
      setTimeRange,
      setScenarioView,
      setGranularity,
      toggleCategory,
      toggleAllCategories,
      setCategoryFilters,
      applyScenario,
      removeScenario,
      clearAllScenarios,
      setIsLoading,
      setIsScenarioLoading,
      togglePanel,
      setError,
    }),
    [
      forecast,
      scenarios,
      suggestions,
      timeRange,
      scenarioView,
      granularity,
      categoryFilters,
      appliedScenarios,
      isLoading,
      isScenarioLoading,
      isPanelCollapsed,
      error,
      toggleCategory,
      toggleAllCategories,
      applyScenario,
      removeScenario,
      clearAllScenarios,
      togglePanel,
    ]
  );

  return (
    <UnifiedForecastContext.Provider value={value}>
      {children}
    </UnifiedForecastContext.Provider>
  );
}

export function useUnifiedForecastContext() {
  const context = useContext(UnifiedForecastContext);
  if (context === undefined) {
    throw new Error('useUnifiedForecastContext must be used within a UnifiedForecastProvider');
  }
  return context;
}

// Export computed helpers
export function useVisibleCategoryIds() {
  const { categoryFilters } = useUnifiedForecastContext();
  return useMemo(
    () => new Set(categoryFilters.filter(f => f.visible).map(f => f.id)),
    [categoryFilters]
  );
}

export function useAllCategoriesToggle() {
  const { categoryFilters } = useUnifiedForecastContext();

  const allIncomeVisible = useMemo(() => {
    const incomeFilters = categoryFilters.filter(f => f.type === 'income');
    return incomeFilters.length > 0 && incomeFilters.every(f => f.visible);
  }, [categoryFilters]);

  const allCostsVisible = useMemo(() => {
    const costFilters = categoryFilters.filter(f => f.type === 'cost');
    return costFilters.length > 0 && costFilters.every(f => f.visible);
  }, [categoryFilters]);

  return { allIncomeVisible, allCostsVisible };
}
