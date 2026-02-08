import { useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { getForecast } from '@/lib/api/forecast';
import { getScenarios, getScenarioSuggestions, getScenarioForecast } from '@/lib/api/scenarios';
import { transformForecastToProjections } from '@/components/projections/types';
import type { ScenarioSuggestion, Scenario, ForecastResponse } from '@/lib/api/types';
import {
  useUnifiedForecastContext,
  type CategoryFilter,
  type AppliedScenario,
  getScenarioColor,
} from './UnifiedForecastContext';

// ============================================================================
// Helper: Extract categories from forecast
// ============================================================================

function extractCategoriesFromForecast(forecast: ForecastResponse): CategoryFilter[] {
  const incomeMap = new Map<string, CategoryFilter>();
  const costMap = new Map<string, CategoryFilter>();

  forecast.weeks.forEach(week => {
    week.events.forEach(event => {
      const name = event.source_name || event.category || 'Other';
      const id = `${event.direction}-${name}`;
      const map = event.direction === 'in' ? incomeMap : costMap;

      if (!map.has(id)) {
        map.set(id, {
          id,
          name,
          type: event.direction === 'in' ? 'income' : 'cost',
          visible: true, // Default to visible
        });
      }
    });
  });

  return [...incomeMap.values(), ...costMap.values()];
}

// ============================================================================
// Hook: useUnifiedForecast
// ============================================================================

export function useUnifiedForecast() {
  const { user } = useAuth();
  const {
    forecast,
    scenarios,
    suggestions,
    timeRange,
    appliedScenarios,
    categoryFilters,
    isLoading,
    isScenarioLoading,
    setForecast,
    setScenarios,
    setSuggestions,
    setCategoryFilters,
    setIsLoading,
    setIsScenarioLoading,
    setError,
    applyScenario,
    removeScenario,
  } = useUnifiedForecastContext();

  // ============================================================================
  // Fetch base data
  // ============================================================================

  const fetchForecast = useCallback(async () => {
    if (!user?.id) return;

    setIsLoading(true);
    setError(null);

    try {
      const weeks = parseInt(timeRange, 10);
      const forecastData = await getForecast(user.id, weeks);
      setForecast(forecastData);

      // Extract and set category filters (preserve visibility state)
      const newCategories = extractCategoriesFromForecast(forecastData);
      // Preserve visibility state from existing filters
      if (categoryFilters.length > 0) {
        const existingVisibility = new Map(categoryFilters.map(f => [f.id, f.visible]));
        const mergedCategories = newCategories.map(cat => ({
          ...cat,
          visible: existingVisibility.has(cat.id) ? existingVisibility.get(cat.id)! : true,
        }));
        setCategoryFilters(mergedCategories);
      } else {
        setCategoryFilters(newCategories);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load forecast');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id, timeRange, setForecast, setCategoryFilters, setIsLoading, setError]);

  const fetchScenarios = useCallback(async () => {
    if (!user?.id) return;

    try {
      const [savedScenarios, suggestionsData] = await Promise.all([
        getScenarios(user.id, 'saved'),
        getScenarioSuggestions(user.id),
      ]);
      setScenarios(savedScenarios);
      setSuggestions(suggestionsData.suggestions);
    } catch (err) {
      // Don't fail the whole page if scenarios fail
      console.error('Failed to load scenarios:', err);
    }
  }, [user?.id, setScenarios, setSuggestions]);

  // ============================================================================
  // Scenario handlers
  // ============================================================================

  const runScenario = useCallback(
    async (scenario: Scenario) => {
      if (!user?.id) return;

      setIsScenarioLoading(true);
      try {
        const comparison = await getScenarioForecast(scenario.id);
        const tableData = transformForecastToProjections(comparison.scenario_forecast);

        const appliedScenario: AppliedScenario = {
          id: scenario.id,
          name: scenario.name,
          color: getScenarioColor(appliedScenarios.length),
          comparison,
          tableData,
        };

        applyScenario(appliedScenario);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to run scenario');
      } finally {
        setIsScenarioLoading(false);
      }
    },
    [user?.id, appliedScenarios.length, applyScenario, setIsScenarioLoading, setError]
  );

  const runSuggestedScenario = useCallback(
    async (suggestion: ScenarioSuggestion) => {
      if (!user?.id) return;

      // For suggested scenarios, we need to create/seed it first, then run
      // For now, we'll create a temporary scenario and run it
      // This can be expanded to use the pipeline endpoints

      setIsScenarioLoading(true);
      try {
        // Create scenario from suggestion
        const { createScenario, buildScenario } = await import('@/lib/api/scenarios');

        const newScenario = await createScenario({
          user_id: user.id,
          name: suggestion.name,
          description: suggestion.description,
          scenario_type: suggestion.scenario_type,
          entry_path: 'tamio_suggested',
          suggested_reason: suggestion.risk_context || undefined,
          source_alert_id: suggestion.source_alert_id || undefined,
          source_detection_type: suggestion.source_detection_type || undefined,
          scope_config: {},
          parameters: suggestion.prefill_params,
        });

        // Build the scenario events
        await buildScenario(newScenario.id);

        // Get the comparison
        const comparison = await getScenarioForecast(newScenario.id);
        const tableData = transformForecastToProjections(comparison.scenario_forecast);

        const appliedScenario: AppliedScenario = {
          id: newScenario.id,
          name: newScenario.name,
          color: getScenarioColor(appliedScenarios.length),
          comparison,
          tableData,
        };

        applyScenario(appliedScenario);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to run scenario');
      } finally {
        setIsScenarioLoading(false);
      }
    },
    [user?.id, appliedScenarios.length, applyScenario, setIsScenarioLoading, setError]
  );

  // ============================================================================
  // Initial fetch
  // ============================================================================

  useEffect(() => {
    fetchForecast();
  }, [fetchForecast]);

  useEffect(() => {
    fetchScenarios();
  }, [fetchScenarios]);

  // ============================================================================
  // Return
  // ============================================================================

  return {
    // Data
    forecast,
    scenarios,
    suggestions,
    appliedScenarios,
    categoryFilters,

    // State
    isLoading,
    isScenarioLoading,

    // Actions
    fetchForecast,
    fetchScenarios,
    runScenario,
    runSuggestedScenario,
    removeScenario,
  };
}
