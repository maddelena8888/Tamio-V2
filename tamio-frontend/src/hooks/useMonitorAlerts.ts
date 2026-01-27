/**
 * Hook for fetching alerts filtered by monitor category (obligations/receivables)
 */

import { useState, useCallback } from 'react';
import { getRisks, type Risk } from '@/lib/api/alertsActions';

export type MonitorCategory = 'obligations' | 'receivables';

export interface UseMonitorAlertsReturn {
  alerts: Risk[];
  isLoading: boolean;
  error: string | null;
  fetchAlerts: (category: MonitorCategory) => Promise<void>;
}

export function useMonitorAlerts(): UseMonitorAlertsReturn {
  const [alerts, setAlerts] = useState<Risk[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAlerts = useCallback(async (category: MonitorCategory) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getRisks({ category, status: 'active' });
      setAlerts(response.risks);
    } catch (err) {
      console.error(`Failed to fetch ${category} alerts:`, err);
      setError(`Failed to load ${category} alerts`);
      setAlerts([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { alerts, isLoading, error, fetchAlerts };
}
