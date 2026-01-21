/**
 * Alerts & Actions Context - V4 Risk/Controls Architecture
 *
 * Provides shared state for the Alerts & Actions page:
 * - Risk and control data
 * - Cross-highlighting between risks and controls
 * - Tammy panel state with risk preloading
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useEffect,
  type ReactNode,
} from 'react';
import {
  getRisks,
  getControls,
  type Risk,
  type Control,
  type RiskFilters,
  type ControlFilters,
  type DecisionItem,
  type DecisionQueueSummary,
} from '@/lib/api/alertsActions';
import { buildDecisionQueue, filterBySection } from '@/lib/utils/decisionQueue';
import { useAuth } from './AuthContext';

// ============================================================================
// Types
// ============================================================================

interface AlertsActionsContextValue {
  // Data
  risks: Risk[];
  controls: Control[];
  isLoading: boolean;
  error: string | null;

  // Decision Queue (new)
  decisionQueue: DecisionItem[];
  decisionQueueSummary: DecisionQueueSummary;
  requiresDecisionItems: DecisionItem[];
  beingHandledItems: DecisionItem[];
  monitoringItems: DecisionItem[];

  // Filters
  riskFilters: RiskFilters;
  controlFilters: ControlFilters;
  setRiskFilters: (filters: RiskFilters) => void;
  setControlFilters: (filters: ControlFilters) => void;

  // Selection for cross-highlighting
  selectedRiskId: string | null;
  selectedControlId: string | null;
  setSelectedRiskId: (id: string | null) => void;
  setSelectedControlId: (id: string | null) => void;

  // Computed highlighting
  highlightedRiskIds: Set<string>;
  highlightedControlIds: Set<string>;

  // Bidirectional linking maps
  riskControlMap: Map<string, string[]>;
  controlRiskMap: Map<string, string[]>;

  // Tammy panel state
  isTammyOpen: boolean;
  tammyPreloadedRisk: Risk | null;
  tammySessionId: string | null;
  openTammyWithRisk: (risk: Risk) => void;
  openTammy: () => void;
  closeTammy: () => void;
  setTammySessionId: (sessionId: string | null) => void;

  // Actions
  refreshData: () => Promise<void>;
  getRiskById: (id: string) => Risk | undefined;
  getControlById: (id: string) => Control | undefined;
}

const AlertsActionsContext = createContext<AlertsActionsContextValue | undefined>(undefined);

// ============================================================================
// Provider
// ============================================================================

interface AlertsActionsProviderProps {
  children: ReactNode;
}

export function AlertsActionsProvider({ children }: AlertsActionsProviderProps) {
  const { user } = useAuth();

  // Data state
  const [risks, setRisks] = useState<Risk[]>([]);
  const [controls, setControls] = useState<Control[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [riskFilters, setRiskFilters] = useState<RiskFilters>({
    severity: 'all',
    timing: 'all',
    status: 'all',
  });
  const [controlFilters, setControlFilters] = useState<ControlFilters>({
    state: 'all',
  });

  // Selection state for cross-highlighting
  const [selectedRiskId, setSelectedRiskId] = useState<string | null>(null);
  const [selectedControlId, setSelectedControlId] = useState<string | null>(null);

  // Tammy panel state
  const [isTammyOpen, setIsTammyOpen] = useState(false);
  const [tammyPreloadedRisk, setTammyPreloadedRisk] = useState<Risk | null>(null);
  const [tammySessionId, setTammySessionId] = useState<string | null>(() => {
    // Restore from localStorage if available
    if (typeof window !== 'undefined' && user?.id) {
      return localStorage.getItem(`tammy_alerts_session_${user.id}`);
    }
    return null;
  });

  // Build bidirectional linking maps
  const { riskControlMap, controlRiskMap } = useMemo(() => {
    const riskControlMap = new Map<string, string[]>();
    const controlRiskMap = new Map<string, string[]>();

    // Build from risks
    risks.forEach((risk) => {
      riskControlMap.set(risk.id, risk.linked_control_ids || []);
    });

    // Build from controls
    controls.forEach((control) => {
      control.linked_risk_ids.forEach((riskId) => {
        // Control -> Risks
        const existingRisks = controlRiskMap.get(control.id) || [];
        if (!existingRisks.includes(riskId)) {
          controlRiskMap.set(control.id, [...existingRisks, riskId]);
        }

        // Risk -> Controls (ensure bidirectional)
        const existingControls = riskControlMap.get(riskId) || [];
        if (!existingControls.includes(control.id)) {
          riskControlMap.set(riskId, [...existingControls, control.id]);
        }
      });
    });

    return { riskControlMap, controlRiskMap };
  }, [risks, controls]);

  // Compute highlighted IDs based on selection
  const highlightedRiskIds = useMemo(() => {
    if (!selectedControlId) return new Set<string>();
    return new Set(controlRiskMap.get(selectedControlId) || []);
  }, [selectedControlId, controlRiskMap]);

  const highlightedControlIds = useMemo(() => {
    if (!selectedRiskId) return new Set<string>();
    return new Set(riskControlMap.get(selectedRiskId) || []);
  }, [selectedRiskId, riskControlMap]);

  // Build decision queue from risks and controls
  const { items: decisionQueue, summary: decisionQueueSummary } = useMemo(() => {
    return buildDecisionQueue(risks, controls, riskControlMap);
  }, [risks, controls, riskControlMap]);

  // Filter items by section for easy access
  const requiresDecisionItems = useMemo(() => {
    return filterBySection(decisionQueue, 'requires_decision');
  }, [decisionQueue]);

  const beingHandledItems = useMemo(() => {
    return filterBySection(decisionQueue, 'being_handled');
  }, [decisionQueue]);

  const monitoringItems = useMemo(() => {
    return filterBySection(decisionQueue, 'monitoring');
  }, [decisionQueue]);

  // Data fetching
  const fetchData = useCallback(async () => {
    if (!user) return;

    setIsLoading(true);
    setError(null);

    try {
      const [risksResponse, controlsResponse] = await Promise.all([
        getRisks(riskFilters),
        getControls(controlFilters),
      ]);

      setRisks(risksResponse.risks);
      setControls(controlsResponse.controls);
    } catch (err) {
      console.error('Failed to fetch alerts/actions data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  }, [user, riskFilters, controlFilters]);

  // Initial fetch and refetch on filter change
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Persist Tammy session ID
  useEffect(() => {
    if (user?.id && tammySessionId) {
      localStorage.setItem(`tammy_alerts_session_${user.id}`, tammySessionId);
    }
  }, [user?.id, tammySessionId]);

  // Tammy panel actions
  const openTammyWithRisk = useCallback((risk: Risk) => {
    setTammyPreloadedRisk(risk);
    setIsTammyOpen(true);
  }, []);

  const openTammy = useCallback(() => {
    setTammyPreloadedRisk(null);
    setIsTammyOpen(true);
  }, []);

  const closeTammy = useCallback(() => {
    setIsTammyOpen(false);
    // Don't clear preloaded risk immediately to allow animations
    setTimeout(() => setTammyPreloadedRisk(null), 300);
  }, []);

  // Helper functions
  const getRiskById = useCallback(
    (id: string) => risks.find((r) => r.id === id),
    [risks]
  );

  const getControlById = useCallback(
    (id: string) => controls.find((c) => c.id === id),
    [controls]
  );

  const refreshData = useCallback(async () => {
    await fetchData();
  }, [fetchData]);

  // Clear selection when clicking outside
  const handleSetSelectedRiskId = useCallback((id: string | null) => {
    setSelectedRiskId(id);
    // Clear control selection when selecting a risk
    if (id) setSelectedControlId(null);
  }, []);

  const handleSetSelectedControlId = useCallback((id: string | null) => {
    setSelectedControlId(id);
    // Clear risk selection when selecting a control
    if (id) setSelectedRiskId(null);
  }, []);

  const value: AlertsActionsContextValue = {
    // Data
    risks,
    controls,
    isLoading,
    error,

    // Decision Queue
    decisionQueue,
    decisionQueueSummary,
    requiresDecisionItems,
    beingHandledItems,
    monitoringItems,

    // Filters
    riskFilters,
    controlFilters,
    setRiskFilters,
    setControlFilters,

    // Selection
    selectedRiskId,
    selectedControlId,
    setSelectedRiskId: handleSetSelectedRiskId,
    setSelectedControlId: handleSetSelectedControlId,

    // Highlighting
    highlightedRiskIds,
    highlightedControlIds,

    // Linking maps
    riskControlMap,
    controlRiskMap,

    // Tammy panel
    isTammyOpen,
    tammyPreloadedRisk,
    tammySessionId,
    openTammyWithRisk,
    openTammy,
    closeTammy,
    setTammySessionId,

    // Actions
    refreshData,
    getRiskById,
    getControlById,
  };

  return (
    <AlertsActionsContext.Provider value={value}>
      {children}
    </AlertsActionsContext.Provider>
  );
}

// ============================================================================
// Hook
// ============================================================================

export function useAlertsActions() {
  const context = useContext(AlertsActionsContext);
  if (context === undefined) {
    throw new Error('useAlertsActions must be used within an AlertsActionsProvider');
  }
  return context;
}

// ============================================================================
// Utility Hook for Tammy Chat Integration
// ============================================================================

/**
 * Format a risk for sending to Tammy as context
 */
export function formatRiskForTammy(risk: Risk): string {
  const parts = [
    `I need help with this risk: "${risk.title}"`,
    '',
    `Severity: ${risk.severity}`,
    `Detected: ${new Date(risk.detected_at).toLocaleDateString()}`,
  ];

  if (risk.cash_impact) {
    parts.push(`Cash impact: $${Math.abs(risk.cash_impact).toLocaleString()}`);
  }

  if (risk.primary_driver) {
    parts.push(`Primary driver: ${risk.primary_driver}`);
  }

  if (risk.context_bullets.length > 0) {
    parts.push('', 'Context:');
    risk.context_bullets.forEach((bullet) => {
      parts.push(`- ${bullet}`);
    });
  }

  parts.push('', 'What are my options?');

  return parts.join('\n');
}
