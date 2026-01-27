import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import type { HealthRingData, HealthStatus } from '@/lib/api/health';
import type { RingMetric } from './HealthRing';

// ============================================================================
// Types
// ============================================================================

export interface MetricExplanationDialogProps {
  /** Which metric to explain (null = dialog closed) */
  metric: RingMetric | null;
  /** The data for the currently selected metric */
  data: HealthRingData | null;
  /** Called when dialog should close */
  onClose: () => void;
}

// ============================================================================
// Status Colors (matches HealthRing)
// ============================================================================

const STATUS_COLORS: Record<HealthStatus, string> = {
  good: '#C5FF35',     // Lime green
  warning: '#FFD6F0',  // Pink
  critical: '#FF6B6B', // Red
};

// ============================================================================
// Metric Content Configuration
// ============================================================================

interface MetricContent {
  title: string;
  question: string;
  description: string;
  formula: string;
  unit: string;
  thresholds: {
    good: string;
    warning: string;
    critical: string;
  };
}

const METRIC_CONTENT: Record<RingMetric, MetricContent> = {
  runway: {
    title: 'Runway',
    question: 'How long can we last?',
    description:
      'Runway measures how many weeks your business can continue operating at the current burn rate before running out of cash. This is your survival metric.',
    formula: 'Current Cash ÷ Weekly Burn Rate',
    unit: 'weeks',
    thresholds: {
      good: '12+ weeks — Strong position with time to plan',
      warning: '6-11 weeks — Below target, monitor closely',
      critical: 'Under 6 weeks — Urgent action needed',
    },
  },
  liquidity: {
    title: 'Liquidity',
    question: 'Can we meet our obligations?',
    description:
      'Liquidity (working capital ratio) measures your ability to cover upcoming expenses with available cash and expected income. A ratio above 1.0 means you can cover your near-term obligations.',
    formula: '(Cash + 30-day Receivables) ÷ (30-day Payables)',
    unit: 'ratio',
    thresholds: {
      good: '1.5+ — Strong liquidity, comfortable buffer',
      warning: '1.0-1.49 — Moderate, watch cash flow timing',
      critical: 'Under 1.0 — Liquidity stress, may struggle to pay bills',
    },
  },
  cash_velocity: {
    title: 'Cash Velocity',
    question: 'How fast do we turn work into cash?',
    description:
      'Cash velocity measures how quickly money flows through your business—the gap between when you pay expenses and when you collect from clients. Lower is better.',
    formula: 'Days Sales Outstanding − Days Payable Outstanding',
    unit: 'days',
    thresholds: {
      good: '30 days or less — Efficient cash conversion',
      warning: '31-60 days — Slow conversion, room to improve',
      critical: 'Over 60 days — Very slow, cash is stuck',
    },
  },
};

// ============================================================================
// Helper Functions
// ============================================================================

function getScoreInterpretation(
  metric: RingMetric,
  value: number,
  status: string
): string {
  const content = METRIC_CONTENT[metric];

  if (metric === 'runway') {
    if (status === 'good') {
      return `With ${Math.round(value)} weeks of runway, you have a strong buffer. Use this time to grow strategically.`;
    } else if (status === 'warning') {
      return `At ${Math.round(value)} weeks, you're below the recommended 12-week buffer. Consider extending runway.`;
    } else {
      return `Only ${Math.round(value)} weeks remaining. Take immediate action to extend runway or secure funding.`;
    }
  }

  if (metric === 'liquidity') {
    if (status === 'good') {
      return `A ratio of ${value.toFixed(1)} means you have ${((value - 1) * 100).toFixed(0)}% more resources than needed to cover obligations.`;
    } else if (status === 'warning') {
      return `A ratio of ${value.toFixed(1)} means you can just cover obligations. Improve by collecting faster or extending payables.`;
    } else {
      return `A ratio of ${value.toFixed(1)} means you may not cover all obligations. Prioritize collections and manage payables.`;
    }
  }

  if (metric === 'cash_velocity') {
    if (status === 'good') {
      return `At ${Math.round(value)} days, your cash conversion is efficient. Money comes in nearly as fast as it goes out.`;
    } else if (status === 'warning') {
      return `At ${Math.round(value)} days, cash is taking longer to flow through. Consider tighter payment terms or incentives for early payment.`;
    } else {
      return `At ${Math.round(value)} days, significant cash is stuck in the cycle. Prioritize collections and review client payment terms.`;
    }
  }

  return '';
}

// ============================================================================
// Component
// ============================================================================

export function MetricExplanationDialog({
  metric,
  data,
  onClose,
}: MetricExplanationDialogProps) {
  if (!metric || !data) return null;

  const content = METRIC_CONTENT[metric];
  const interpretation = getScoreInterpretation(metric, data.value, data.status);

  return (
    <Dialog open={!!metric} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-1">
            {/* Status color indicator */}
            <div
              className="w-4 h-4 rounded-full flex-shrink-0"
              style={{ backgroundColor: STATUS_COLORS[data.status] }}
            />
            <DialogTitle className="text-xl">{content.title}</DialogTitle>
          </div>
          <DialogDescription className="text-base font-medium text-gunmetal">
            {content.question}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {/* Current Score */}
          <div className="rounded-xl p-4 bg-muted/50">
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-3xl font-bold text-gunmetal">
                {data.label}
              </span>
              <span className="text-sm text-muted-foreground">
                {content.unit}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{interpretation}</p>
          </div>

          {/* Description */}
          <div>
            <h4 className="text-sm font-semibold text-gunmetal mb-1.5">
              What it measures
            </h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {content.description}
            </p>
          </div>

          {/* Formula */}
          <div>
            <h4 className="text-sm font-semibold text-gunmetal mb-1.5">
              Formula
            </h4>
            <code className="block text-sm bg-muted px-3 py-2 rounded-lg font-mono">
              {content.formula}
            </code>
          </div>

          {/* Thresholds */}
          <div>
            <h4 className="text-sm font-semibold text-gunmetal mb-2">
              Thresholds
            </h4>
            <div className="space-y-1.5">
              <div className="flex items-start gap-2">
                <span
                  className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                  style={{ backgroundColor: STATUS_COLORS.good }}
                />
                <span className="text-sm text-muted-foreground">
                  {content.thresholds.good}
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span
                  className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                  style={{ backgroundColor: STATUS_COLORS.warning }}
                />
                <span className="text-sm text-muted-foreground">
                  {content.thresholds.warning}
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span
                  className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                  style={{ backgroundColor: STATUS_COLORS.critical }}
                />
                <span className="text-sm text-muted-foreground">
                  {content.thresholds.critical}
                </span>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default MetricExplanationDialog;
