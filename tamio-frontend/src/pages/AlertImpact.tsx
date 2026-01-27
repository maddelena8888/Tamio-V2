import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useTAMIPageContext } from '@/contexts/TAMIContext';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { toast } from 'sonner';
import {
  ImpactHeader,
  ImpactVisualization,
  FixOptionsRow,
  ScenarioBuilderLink,
  TAMIFloatingButton,
  type FixRecommendation,
  type DangerZone,
} from '@/components/impact';
import {
  getRisk,
  getControlsForRisk,
  approveControl,
  type Risk,
  type Control,
} from '@/lib/api/alertsActions';
import { getForecast } from '@/lib/api/forecast';
import type { ForecastResponse, ScenarioType } from '@/lib/api/types';

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
 * Uses the lowest_cash_amount as a proxy if no explicit buffer.
 */
function getBufferAmount(forecast: ForecastResponse): number {
  // Use 20% of starting cash as a reasonable buffer threshold
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
  linkedControls: Control[]
): FixRecommendation[] {
  const fixes: FixRecommendation[] = [];

  // 1. Add linked controls as fixes (highest priority)
  for (const control of linkedControls) {
    if (fixes.length >= 3) break;
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
  if (fixes.length < 3) {
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
      if (fixes.length >= 3) break;
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
  if (fixes.length < 3) {
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

  return fixes.slice(0, 3);
}

// ============================================================================
// Component
// ============================================================================

export default function AlertImpact() {
  const { alertId } = useParams<{ alertId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  // State
  const [alert, setAlert] = useState<Risk | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [linkedControls, setLinkedControls] = useState<Control[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isTamiOpen, setIsTamiOpen] = useState(false);

  // Register page context for TAMI
  useTAMIPageContext({
    page: 'alert-impact',
    pageData: alert
      ? {
          currentAlert: {
            id: alert.id,
            title: alert.title,
            severity: alert.severity,
          },
        }
      : undefined,
  });

  // Fetch all required data
  useEffect(() => {
    async function fetchData() {
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
      } catch (err) {
        console.error('Failed to fetch impact data:', err);
        setError('Failed to load alert impact data');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [alertId, user?.id]);

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
    return generateFixRecommendations(alert, linkedControls);
  }, [alert, linkedControls]);

  // Handlers
  const handleShare = useCallback(async () => {
    const shareUrl = window.location.href;

    try {
      if (navigator.share) {
        await navigator.share({
          title: `Tamio Alert: ${alert?.title || 'Alert Impact'}`,
          text: 'View the cash flow impact of this alert',
          url: shareUrl,
        });
      } else {
        await navigator.clipboard.writeText(shareUrl);
        toast.success('Link copied to clipboard');
      }
    } catch (err) {
      // User cancelled share or copy failed
      console.error('Share failed:', err);
    }
  }, [alert?.title]);

  const handleSelectFix = useCallback(
    async (fix: FixRecommendation) => {
      switch (fix.action.type) {
        case 'approve_control': {
          try {
            await approveControl(fix.action.payload.controlId as string);
            toast.success('Fix approved successfully');
            // Refresh controls
            if (alertId) {
              const controls = await getControlsForRisk(alertId);
              setLinkedControls(controls);
            }
          } catch (err) {
            console.error('Failed to approve control:', err);
            toast.error('Failed to approve fix');
          }
          break;
        }
        case 'run_scenario': {
          const params = new URLSearchParams();
          params.set('type', fix.action.payload.type as string);
          if (fix.action.payload.alertId) {
            params.set('alertId', fix.action.payload.alertId as string);
          }
          navigate(`/scenarios?${params.toString()}`);
          break;
        }
        case 'open_builder': {
          const params = new URLSearchParams();
          if (fix.action.payload.alertId) {
            params.set('alertId', fix.action.payload.alertId as string);
          }
          navigate(`/scenarios?${params.toString()}`);
          break;
        }
      }
    },
    [alertId, navigate]
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-[calc(100vh-8rem)] p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  // Error state
  if (error || !alert || !forecast) {
    return (
      <div className="min-h-[calc(100vh-8rem)] flex flex-col items-center justify-center p-6">
        <p className="text-lg text-muted-foreground mb-4">{error || 'Alert not found'}</p>
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-gunmetal hover:text-gunmetal/80 underline"
        >
          Go back
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-8rem)] p-6 max-w-6xl mx-auto">
      {/* Header with back, title, share */}
      <ImpactHeader alert={alert} onShare={handleShare} />

      {/* Main visualization - shows current forecast vs impacted scenario */}
      <ImpactVisualization
        forecast={forecast}
        dangerZone={dangerZone}
        alertWeek={alertWeek}
        bufferAmount={bufferAmount}
        alertImpact={alert.cash_impact}
        impactWeek={alertWeek}
      />

      {/* Fix options */}
      <FixOptionsRow fixes={fixes} onSelectFix={handleSelectFix} />

      {/* Scenario builder link */}
      <ScenarioBuilderLink alertId={alertId} />

      {/* TAMI floating button */}
      <TAMIFloatingButton onClick={() => setIsTamiOpen(true)} />

      {/* TAMI Chat Sheet */}
      <Sheet open={isTamiOpen} onOpenChange={setIsTamiOpen}>
        <SheetContent className="w-[400px] sm:w-[540px]">
          <SheetHeader>
            <SheetTitle>Chat with TAMI</SheetTitle>
          </SheetHeader>
          <div className="mt-4 h-full flex flex-col">
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <p className="text-center">
                TAMI chat integration coming soon.
                <br />
                <span className="text-sm">
                  For now, visit the{' '}
                  <button
                    onClick={() => {
                      setIsTamiOpen(false);
                      navigate('/tami');
                    }}
                    className="text-gunmetal underline"
                  >
                    TAMI page
                  </button>{' '}
                  to chat about this alert.
                </span>
              </p>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

// ============================================================================
// Loading Skeleton
// ============================================================================

function LoadingSkeleton() {
  return (
    <div className="max-w-6xl mx-auto">
      {/* Header skeleton */}
      <div className="flex items-center justify-between mb-8">
        <Skeleton className="h-10 w-20" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-10 w-24" />
      </div>

      {/* Chart skeleton */}
      <div className="alert-hero-glass rounded-3xl p-8 mb-8">
        <Skeleton className="h-[350px] w-full bg-white/30" />
      </div>

      {/* Fix options skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-6 rounded-2xl bg-white/40 backdrop-blur-md">
            <Skeleton className="h-6 w-16 mx-auto mb-4" />
            <Skeleton className="h-5 w-32 mx-auto mb-2" />
            <Skeleton className="h-4 w-full mb-4" />
            <Skeleton className="h-10 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
