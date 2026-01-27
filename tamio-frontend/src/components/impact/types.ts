import type { Control } from '@/lib/api/alertsActions';
import type { ScenarioType } from '@/lib/api/types';

/**
 * Fix recommendation for the Alert Impact page.
 * Can come from linked controls or auto-generated scenarios.
 */
export interface FixRecommendation {
  id: string;
  type: 'control' | 'scenario';
  title: string;
  description: string;
  impact_amount: number | null;
  buffer_improvement: string | null; // e.g., "+2 weeks buffer", "+$50K"
  source: Control | { scenario_type: ScenarioType } | null;
  action: {
    type: 'approve_control' | 'run_scenario' | 'open_builder';
    payload: Record<string, unknown>;
  };
}

/**
 * Danger zone information computed from forecast data.
 */
export interface DangerZone {
  startWeek: number;
  endWeek: number;
  lowestPoint: {
    week: number;
    amount: number;
  };
  belowBufferWeeks: number[];
}

/**
 * Chart data point for the impact visualization.
 */
export interface ImpactChartData {
  week: string;
  weekNumber: number;
  position: number;
  impactedPosition?: number; // Position if alert impact materializes
  buffer: number;
  isBelowBuffer: boolean;
  isImpactedBelowBuffer?: boolean;
}
