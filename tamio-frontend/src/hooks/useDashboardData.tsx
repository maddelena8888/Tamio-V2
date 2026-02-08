/**
 * Dashboard Data Hook - Aggregated data fetching for dashboard widgets
 *
 * Provides a single source of data for all widgets via context to avoid
 * prop drilling and redundant API calls.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useHealthData } from './useHealthData';
import { getForecast } from '@/lib/api/forecast';
import { getCashPosition } from '@/lib/api/data';
import { getRisks } from '@/lib/api/alertsActions';
import type { ForecastResponse, CashPositionResponse } from '@/lib/api/types';
import type { Risk } from '@/lib/api/alertsActions';
import type { WidgetData } from '@/components/dashboard/widgets/types';

// ============================================================================
// Context
// ============================================================================

const WidgetDataContext = createContext<WidgetData | undefined>(undefined);

// ============================================================================
// Hook Implementation
// ============================================================================

interface UseDashboardDataReturn extends WidgetData {
  // Additional methods can be added here
}

/**
 * Hook for fetching aggregated dashboard data.
 * Combines health metrics, forecast, cash position, and risks.
 */
export function useDashboardData(): UseDashboardDataReturn {
  const { user } = useAuth();

  // Use existing health data hook with polling
  const {
    data: healthData,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
  } = useHealthData({ pollingInterval: 60000 });

  // Additional data state
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [cashPosition, setCashPosition] = useState<CashPositionResponse | null>(null);
  const [risksData, setRisksData] = useState<Risk[] | null>(null);
  const [additionalLoading, setAdditionalLoading] = useState(true);
  const [additionalError, setAdditionalError] = useState<string | null>(null);

  // Fetch additional data
  const fetchAdditionalData = useCallback(async () => {
    if (!user?.id) {
      setAdditionalLoading(false);
      return;
    }

    setAdditionalLoading(true);
    setAdditionalError(null);

    try {
      const [forecast, cash, risks] = await Promise.all([
        getForecast(user.id, 13).catch(() => null),
        getCashPosition(user.id).catch(() => null),
        getRisks({ status: 'active' }).catch(() => ({ risks: [] })),
      ]);

      setForecastData(forecast);
      setCashPosition(cash);
      setRisksData(risks?.risks ?? []);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setAdditionalError('Failed to load some dashboard data');
    } finally {
      setAdditionalLoading(false);
    }
  }, [user?.id]);

  // Initial fetch of additional data
  useEffect(() => {
    fetchAdditionalData();
  }, [fetchAdditionalData]);

  // Combined refetch function
  const refetch = useCallback(() => {
    refetchHealth();
    fetchAdditionalData();
  }, [refetchHealth, fetchAdditionalData]);

  // Combined loading and error states
  const isLoading = healthLoading || additionalLoading;
  const error = healthError || additionalError;

  return {
    healthData,
    forecastData,
    cashPosition,
    risksData,
    isLoading,
    error,
    refetch,
  };
}

// ============================================================================
// Provider Component
// ============================================================================

interface WidgetDataProviderProps {
  children: ReactNode;
}

/**
 * Provider component that wraps dashboard and provides widget data context.
 */
export function WidgetDataProvider({ children }: WidgetDataProviderProps) {
  const data = useDashboardData();

  return <WidgetDataContext.Provider value={data}>{children}</WidgetDataContext.Provider>;
}

// ============================================================================
// Consumer Hook
// ============================================================================

/**
 * Hook for widgets to access dashboard data.
 * Must be used within a WidgetDataProvider.
 */
export function useWidgetData(): WidgetData {
  const context = useContext(WidgetDataContext);
  if (!context) {
    throw new Error('useWidgetData must be used within a WidgetDataProvider');
  }
  return context;
}
