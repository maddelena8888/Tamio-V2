import { useState, useEffect, useMemo, useRef } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  getRisk,
  getControlsForRisk,
  type Risk,
  type Control,
} from '@/lib/api/alertsActions';
import { getForecast } from '@/lib/api/forecast';
import type { ForecastResponse, ScenarioType } from '@/lib/api/types';
import type { DangerZone, FixRecommendation } from '@/components/impact/types';

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Compute the danger zone from forecast data.
 * Returns info about weeks where cash position drops below buffer.
 */
function computeDangerZone(
  forecast: ForecastResponse,
  bufferAmount: number
): DangerZone | null {
  const belowBufferWeeks: number[] = [];
  let lowestWeek = 1;
  let lowestAmount = Infinity;

  for (const week of forecast.weeks) {
    const balance = parseFloat(week.ending_balance);
    if (balance < bufferAmount) {
      belowBufferWeeks.push(week.week_number);
    }
    if (balance < lowestAmount) {
      lowestAmount = balance;
      lowestWeek = week.week_number;
    }
  }

  if (belowBufferWeeks.length === 0) {
    return null;
  }

  return {
    startWeek: Math.min(...belowBufferWeeks),
    endWeek: Math.max(...belowBufferWeeks),
    lowestPoint: { week: lowestWeek, amount: lowestAmount },
    belowBufferWeeks,
  };
}

/**
 * Get the alert week from the alert's context data.
 * Falls back to extracting from context_bullets or using week 3.
 */
function getAlertWeek(alert: Risk): number {
  // Try to get from context_data
  const contextData = alert.context_data as Record<string, unknown>;
  if (contextData?.week_number) {
    return contextData.week_number as number;
  }

  // Try to extract from context bullets
  for (const bullet of alert.context_bullets) {
    const weekMatch = bullet.match(/Week\s*(\d+)/i);
    if (weekMatch) {
      return parseInt(weekMatch[1], 10);
    }
  }

  // Default to week 3 (common danger point)
  return 3;
}

/**
 * Get buffer amount from forecast or context.
 * Uses 20% of starting cash as a reasonable buffer threshold.
 */
function getBufferAmount(forecast: ForecastResponse): number {
  const startingCash = parseFloat(forecast.starting_cash);
  return startingCash * 0.2;
}

/**
 * Format compact currency for display
 */
function formatCompactCurrency(amount: number): string {
  if (Math.abs(amount) >= 1000000) {
    return `$${(amount / 1000000).toFixed(1)}M`;
  }
  if (Math.abs(amount) >= 1000) {
    return `$${Math.round(amount / 1000)}K`;
  }
  return `$${amount.toLocaleString()}`;
}

/**
 * Get human-readable scenario title from type
 */
function getScenarioTitle(type: ScenarioType): string {
  const titles: Record<ScenarioType, string> = {
    client_loss: 'Plan for Client Loss',
    client_gain: 'Add New Client',
    client_change: 'Modify Client Terms',
    hiring: 'Plan Hiring',
    firing: 'Reduce Headcount',
    contractor_gain: 'Add Contractor',
    contractor_loss: 'Remove Contractor',
    increased_expense: 'Plan Expense Increase',
    decreased_expense: 'Reduce Expenses',
    payment_delay_in: 'Request Early Payment',
    payment_delay_out: 'Delay Vendor Payment',
  };
  return titles[type] || type;
}

/**
 * Get description for scenario type
 */
function getScenarioDescription(type: ScenarioType): string {
  const descriptions: Record<ScenarioType, string> = {
    client_loss: 'Model the impact of losing a client',
    client_gain: 'Model adding a new revenue source',
    client_change: 'Model changes to existing client terms',
    hiring: 'Model the cost of adding new team members',
    firing: 'Model savings from reducing headcount',
    contractor_gain: 'Model adding contractor costs',
    contractor_loss: 'Model savings from contractor changes',
    increased_expense: 'Model new or increased expenses',
    decreased_expense: 'Model cost reduction opportunities',
    payment_delay_in: 'Request clients pay sooner to improve cash flow',
    payment_delay_out: 'Negotiate later payment terms with vendors',
  };
  return descriptions[type] || '';
}

/**
 * Generate fix recommendations from linked controls and scenario suggestions.
 */
function generateFixRecommendations(
  alert: Risk,
  linkedControls: Control[],
  maxFixes: number = 3
): FixRecommendation[] {
  const fixes: FixRecommendation[] = [];

  // 1. Add linked controls as fixes (highest priority)
  for (const control of linkedControls) {
    if (fixes.length >= maxFixes) break;
    fixes.push({
      id: control.id,
      type: 'control',
      title: control.name,
      description: control.why_it_exists,
      impact_amount: control.impact_amount,
      buffer_improvement: control.impact_amount
        ? `+${formatCompactCurrency(control.impact_amount)}`
        : 'Improves cash position',
      source: control,
      action: {
        type: 'approve_control',
        payload: { controlId: control.id },
      },
    });
  }

  // 2. Generate scenario-based fixes based on alert detection type
  if (fixes.length < maxFixes) {
    const scenarioMappings: Record<string, ScenarioType[]> = {
      payment_overdue: ['payment_delay_out', 'decreased_expense'],
      late_payment: ['payment_delay_out', 'decreased_expense'],
      cash_shortfall: ['payment_delay_out', 'payment_delay_in', 'decreased_expense'],
      buffer_breach: ['payment_delay_out', 'decreased_expense', 'payment_delay_in'],
      high_concentration: ['client_gain', 'payment_delay_in'],
      expense_spike: ['decreased_expense', 'payment_delay_out'],
      payroll_risk: ['payment_delay_out', 'client_gain'],
    };

    const relevantScenarios = scenarioMappings[alert.detection_type] || [
      'payment_delay_out',
      'decreased_expense',
    ];

    for (const scenarioType of relevantScenarios) {
      if (fixes.length >= maxFixes) break;
      fixes.push({
        id: `scenario_${scenarioType}`,
        type: 'scenario',
        title: getScenarioTitle(scenarioType),
        description: getScenarioDescription(scenarioType),
        impact_amount: null,
        buffer_improvement: 'See projection',
        source: { scenario_type: scenarioType },
        action: {
          type: 'run_scenario',
          payload: {
            type: scenarioType,
            alertId: alert.id,
          },
        },
      });
    }
  }

  // 3. Always ensure we have at least one fallback option
  if (fixes.length < maxFixes) {
    fixes.push({
      id: 'custom',
      type: 'scenario',
      title: 'Custom Solution',
      description: 'Build your own scenario to address this alert',
      impact_amount: null,
      buffer_improvement: 'Varies',
      source: null,
      action: {
        type: 'open_builder',
        payload: { alertId: alert.id },
      },
    });
  }

  return fixes.slice(0, maxFixes);
}

// ============================================================================
// Hook Interface
// ============================================================================

export interface UseImpactDataReturn {
  alert: Risk | null;
  forecast: ForecastResponse | null;
  linkedControls: Control[];
  isLoading: boolean;
  error: string | null;
  dangerZone: DangerZone | null;
  bufferAmount: number;
  alertWeek: number;
  fixes: FixRecommendation[];
  refetch: () => Promise<void>;
}

interface UseImpactDataOptions {
  maxFixes?: number;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for fetching and computing alert impact data.
 * Only fetches when shouldFetch is true (lazy loading).
 * Caches results to avoid refetching on collapse/re-expand.
 */
export function useImpactData(
  alertId: string,
  shouldFetch: boolean,
  options: UseImpactDataOptions = {}
): UseImpactDataReturn {
  const { user } = useAuth();
  const { maxFixes = 3 } = options;

  // State
  const [alert, setAlert] = useState<Risk | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [linkedControls, setLinkedControls] = useState<Control[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track if we've fetched to avoid refetching
  const hasFetchedRef = useRef(false);

  // Fetch function
  const fetchData = async () => {
    if (!alertId || !user?.id) return;

    try {
      setIsLoading(true);
      setError(null);

      // Fetch all data in parallel
      const [alertData, forecastData, controls] = await Promise.all([
        getRisk(alertId),
        getForecast(user.id, 13),
        getControlsForRisk(alertId),
      ]);

      setAlert(alertData);
      setForecast(forecastData);
      setLinkedControls(controls);
      hasFetchedRef.current = true;
    } catch (err) {
      console.error('Failed to fetch impact data:', err);
      setError('Failed to load alert impact data');
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch when shouldFetch becomes true (only once)
  useEffect(() => {
    if (shouldFetch && !hasFetchedRef.current && !isLoading) {
      fetchData();
    }
  }, [shouldFetch, alertId, user?.id]);

  // Compute derived values
  const bufferAmount = useMemo(() => {
    if (!forecast) return 0;
    return getBufferAmount(forecast);
  }, [forecast]);

  const dangerZone = useMemo(() => {
    if (!forecast) return null;
    return computeDangerZone(forecast, bufferAmount);
  }, [forecast, bufferAmount]);

  const alertWeek = useMemo(() => {
    if (!alert) return 3;
    return getAlertWeek(alert);
  }, [alert]);

  const fixes = useMemo(() => {
    if (!alert) return [];
    return generateFixRecommendations(alert, linkedControls, maxFixes);
  }, [alert, linkedControls, maxFixes]);

  return {
    alert,
    forecast,
    linkedControls,
    isLoading,
    error,
    dangerZone,
    bufferAmount,
    alertWeek,
    fixes,
    refetch: fetchData,
  };
}
