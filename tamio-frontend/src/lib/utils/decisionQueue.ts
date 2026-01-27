/**
 * Decision Queue Utility
 *
 * Transforms risks and controls into a decision queue structure
 * for the redesigned Alerts & Actions page.
 */

import type {
  Risk,
  Control,
  DecisionItem,
  DecisionQueueSection,
  DecisionQueueSummary,
  AlertData,
  RecommendationData,
} from '@/lib/api/alertsActions';

/**
 * Categorize a risk into the appropriate decision queue section
 * based on its linked controls' states.
 */
function categorizeToSection(
  _risk: Risk,
  linkedControls: Control[]
): DecisionQueueSection {
  const pendingControls = linkedControls.filter((c) => c.state === 'pending');
  const activeControls = linkedControls.filter((c) => c.state === 'active');

  // "Requires Decision": Risk has pending controls awaiting approval
  if (pendingControls.length > 0) {
    return 'requires_decision';
  }

  // "Being Handled": Risk has active controls executing
  if (activeControls.length > 0) {
    return 'being_handled';
  }

  // "Monitoring": Everything else (acknowledged risks, low priority, etc.)
  return 'monitoring';
}

/**
 * Calculate how many days ago a risk was detected
 */
function calculateDaysAgo(detectedAt: string): number {
  const detected = new Date(detectedAt);
  const now = new Date();
  const diffTime = now.getTime() - detected.getTime();
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
}

/**
 * Transform a Risk into AlertData for display
 */
function riskToAlertData(risk: Risk): AlertData {
  return {
    id: risk.id,
    title: risk.title,
    severity: risk.severity,
    detected_at: risk.detected_at,
    deadline: risk.deadline,
    due_horizon_label: risk.due_horizon_label,
    cash_impact: risk.cash_impact,
    buffer_impact_percent: risk.buffer_impact_percent,
    impact_statement: risk.impact_statement,
    primary_driver: risk.primary_driver,
    context_bullets: risk.context_bullets,
    status: risk.status,
  };
}

/**
 * Transform a Control into RecommendationData for display
 */
function controlToRecommendationData(control: Control): RecommendationData {
  return {
    controlId: control.id,
    name: control.name,
    why_it_exists: control.why_it_exists,
    tamio_handles: control.tamio_handles,
    user_handles: control.user_handles,
    impact_amount: control.impact_amount,
    expected_outcome: control.why_it_exists, // Use why_it_exists as expected outcome
  };
}

/**
 * Build the decision queue from risks and controls.
 *
 * This function transforms the separate risk and control data
 * into a unified decision queue structure with three sections:
 * - requires_decision: Risks with pending controls
 * - being_handled: Risks with active controls
 * - monitoring: Risks without pending/active controls
 *
 * @param risks - Array of risks from the API
 * @param controls - Array of controls from the API
 * @param riskControlMap - Map of risk ID to linked control IDs
 * @returns Object containing decision items and summary statistics
 */
export function buildDecisionQueue(
  risks: Risk[],
  controls: Control[],
  riskControlMap: Map<string, string[]>
): {
  items: DecisionItem[];
  summary: DecisionQueueSummary;
} {
  // Build a lookup map for controls by ID
  const controlById = new Map(controls.map((c) => [c.id, c]));

  // Transform each risk into a DecisionItem
  const items: DecisionItem[] = risks.map((risk) => {
    // Get linked controls for this risk
    const linkedControlIds = riskControlMap.get(risk.id) || [];
    const linkedControls = linkedControlIds
      .map((id) => controlById.get(id))
      .filter((c): c is Control => c !== undefined);

    // Separate controls by state
    const pendingControls = linkedControls.filter((c) => c.state === 'pending');
    const activeControls = linkedControls.filter((c) => c.state === 'active');

    // Determine which section this risk belongs to
    const section = categorizeToSection(risk, linkedControls);

    // Get primary recommendation (first pending control)
    const primaryRecommendation = pendingControls[0];

    // Calculate how long ago this was detected/predicted
    const forecastDaysAgo = calculateDaysAgo(risk.detected_at);

    return {
      id: risk.id,
      section,
      alert: riskToAlertData(risk),
      recommendation: primaryRecommendation
        ? controlToRecommendationData(primaryRecommendation)
        : null,
      activeControls,
      forecastDaysAgo,
    };
  });

  // Sort items by severity and deadline within each section
  const sortByUrgency = (a: DecisionItem, b: DecisionItem): number => {
    // First sort by severity (urgent > high > normal)
    const severityOrder = { urgent: 0, high: 1, normal: 2 };
    const severityDiff =
      severityOrder[a.alert.severity] - severityOrder[b.alert.severity];
    if (severityDiff !== 0) return severityDiff;

    // Then sort by cash impact (higher impact first)
    const aImpact = Math.abs(a.alert.cash_impact || 0);
    const bImpact = Math.abs(b.alert.cash_impact || 0);
    return bImpact - aImpact;
  };

  items.sort(sortByUrgency);

  // Compute summary statistics
  const requiresDecisionItems = items.filter(
    (i) => i.section === 'requires_decision'
  );
  const beingHandledItems = items.filter((i) => i.section === 'being_handled');
  const monitoringItems = items.filter((i) => i.section === 'monitoring');

  const summary: DecisionQueueSummary = {
    requires_decision: {
      count: requiresDecisionItems.length,
      total_at_risk: requiresDecisionItems.reduce(
        (sum, i) => sum + Math.abs(i.alert.cash_impact || 0),
        0
      ),
    },
    being_handled: {
      count: beingHandledItems.length,
      has_executing: beingHandledItems.some((i) => i.activeControls.length > 0),
    },
    monitoring: {
      count: monitoringItems.length,
      total_upcoming: monitoringItems.reduce(
        (sum, i) => sum + Math.abs(i.alert.cash_impact || 0),
        0
      ),
    },
  };

  return { items, summary };
}

/**
 * Filter decision items by section
 */
export function filterBySection(
  items: DecisionItem[],
  section: DecisionQueueSection
): DecisionItem[] {
  return items.filter((item) => item.section === section);
}

/**
 * Format currency amount for display
 */
export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  const absValue = Math.abs(value);
  if (absValue >= 1000000) {
    return `$${(absValue / 1000000).toFixed(1)}M`;
  }
  if (absValue >= 1000) {
    return `$${(absValue / 1000).toFixed(0)}K`;
  }
  return `$${absValue.toLocaleString()}`;
}

/**
 * Get border color class based on severity
 */
export function getSeverityBorderClass(
  severity: 'urgent' | 'high' | 'normal'
): string {
  const borderClasses = {
    urgent: 'border-l-tomato',
    high: 'border-l-amber-500',
    normal: 'border-l-lime',
  };
  return borderClasses[severity];
}
