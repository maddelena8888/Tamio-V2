/**
 * useAlertsPanelData Hook
 *
 * Fetches and processes alerts data for the dashboard panel.
 * Reuses existing API functions and decision queue utilities.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { getRisks, getControls, type Risk, type Control } from '@/lib/api/alertsActions';
import { buildDecisionQueue, filterBySection } from '@/lib/utils/decisionQueue';
import type { AlertPanelItem, AlertPanelSummary, UseAlertsPanelDataReturn } from './types';

/**
 * Hook for fetching and processing alerts data for the dashboard panel
 */
export function useAlertsPanelData(): UseAlertsPanelDataReturn {
  const [risks, setRisks] = useState<Risk[]>([]);
  const [controls, setControls] = useState<Control[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch data from API
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [risksResponse, controlsResponse] = await Promise.all([
        getRisks({ status: 'active' }),
        getControls(),
      ]);

      setRisks(risksResponse.risks);
      setControls(controlsResponse.controls);
    } catch (err) {
      console.error('Failed to fetch alerts panel data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load alerts');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch on mount
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Build risk-control mapping
  const riskControlMap = useMemo(() => {
    const map = new Map<string, string[]>();

    // Build from risks
    risks.forEach((risk) => {
      map.set(risk.id, risk.linked_control_ids || []);
    });

    // Ensure bidirectional linking from controls
    controls.forEach((control) => {
      control.linked_risk_ids.forEach((riskId) => {
        const existing = map.get(riskId) || [];
        if (!existing.includes(control.id)) {
          map.set(riskId, [...existing, control.id]);
        }
      });
    });

    return map;
  }, [risks, controls]);

  // Build decision queue using existing utility
  const { items: decisionItems, summary: queueSummary } = useMemo(() => {
    return buildDecisionQueue(risks, controls, riskControlMap);
  }, [risks, controls, riskControlMap]);

  // Transform DecisionItems to AlertPanelItems
  const items: AlertPanelItem[] = useMemo(() => {
    return decisionItems.map((item) => ({
      id: item.id,
      section: item.section,
      alert: {
        id: item.alert.id,
        title: item.alert.title,
        severity: item.alert.severity,
        detected_at: item.alert.detected_at,
        deadline: item.alert.deadline,
        days_until_deadline: null, // Not in AlertData, will need from Risk if needed
        due_horizon_label: item.alert.due_horizon_label,
        cash_impact: item.alert.cash_impact,
        buffer_impact_percent: item.alert.buffer_impact_percent,
        impact_statement: item.alert.impact_statement,
        primary_driver: item.alert.primary_driver,
        status: item.alert.status,
      },
      recommendation: item.recommendation
        ? {
            controlId: item.recommendation.controlId,
            name: item.recommendation.name,
            why_it_exists: item.recommendation.why_it_exists,
          }
        : null,
      activeControls: item.activeControls,
    }));
  }, [decisionItems]);

  // Filter items by section
  const requiresDecision = useMemo(
    () => items.filter((item) => item.section === 'requires_decision'),
    [items]
  );

  const beingHandled = useMemo(
    () => items.filter((item) => item.section === 'being_handled'),
    [items]
  );

  const monitoring = useMemo(
    () => items.filter((item) => item.section === 'monitoring'),
    [items]
  );

  // Transform summary to match our types
  const summary: AlertPanelSummary = useMemo(
    () => ({
      requiresDecision: {
        count: queueSummary.requires_decision.count,
        totalAtRisk: queueSummary.requires_decision.total_at_risk,
      },
      beingHandled: {
        count: queueSummary.being_handled.count,
        hasExecuting: queueSummary.being_handled.has_executing,
      },
      monitoring: {
        count: queueSummary.monitoring.count,
        totalUpcoming: queueSummary.monitoring.total_upcoming,
      },
      total: items.length,
    }),
    [queueSummary, items.length]
  );

  return {
    items,
    requiresDecision,
    beingHandled,
    monitoring,
    summary,
    isLoading,
    error,
    refetch: fetchData,
  };
}
