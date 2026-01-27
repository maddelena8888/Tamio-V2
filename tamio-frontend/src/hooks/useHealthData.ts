import { useState, useEffect, useCallback } from 'react';
import { getHealthMetrics, type HealthMetricsResponse } from '@/lib/api/health';

// ============================================================================
// Hook Interface
// ============================================================================

export interface UseHealthDataReturn {
  data: HealthMetricsResponse | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export interface UseHealthDataOptions {
  /** Enable polling at specified interval in milliseconds */
  pollingInterval?: number;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for fetching health metrics data.
 *
 * @param options Configuration options
 * @returns Health data, loading state, error, and refetch function
 */
export function useHealthData(
  options: UseHealthDataOptions = {}
): UseHealthDataReturn {
  const { pollingInterval } = options;

  // State
  const [data, setData] = useState<HealthMetricsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch function
  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const response = await getHealthMetrics();
      setData(response);
    } catch (err) {
      console.error('Failed to fetch health metrics:', err);
      setError('Failed to load health metrics');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Polling (if enabled)
  useEffect(() => {
    if (!pollingInterval) return;

    const interval = setInterval(fetchData, pollingInterval);
    return () => clearInterval(interval);
  }, [fetchData, pollingInterval]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}
