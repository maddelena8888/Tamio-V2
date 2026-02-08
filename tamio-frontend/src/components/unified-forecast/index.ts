// Context and Hook
export {
  UnifiedForecastProvider,
  useUnifiedForecastContext,
  useVisibleCategoryIds,
  useAllCategoriesToggle,
  SCENARIO_COLORS,
  getScenarioColor,
  type TimeRange,
  type Granularity,
  type CategoryFilter,
  type AppliedScenario,
} from './UnifiedForecastContext';

export { useUnifiedForecast } from './useUnifiedForecast';

// Components
export { IncomeExpenseFilter } from './IncomeExpenseFilter';
export { ExtendedScenarioToggle, CompactScenarioToggle } from './ExtendedScenarioToggle';
export { ValueChangeHighlight, DeltaDisplay, PercentageChange } from './ValueChangeHighlight';
export {
  SuggestedScenarioCard,
  SavedScenarioCard,
  ActiveScenarioBadge,
} from './ScenarioCard';
export { ScenarioPanel, MobileScenarioDrawer } from './ScenarioPanel';
