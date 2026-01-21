import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { NeuroCard, NeuroCardHeader, NeuroCardTitle, NeuroCardContent } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  ChartContainer,
  ChartTooltip,
  type ChartConfig,
} from '@/components/ui/chart';
import { ComposedChart, Area, XAxis, YAxis, Line, CartesianGrid } from 'recharts';
import { ArrowRight, X, Check, FileText, Info } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { getForecast } from '@/lib/api/forecast';
import { getCashPosition } from '@/lib/api/data';
import { getRules } from '@/lib/api/scenarios';
import { getActionQueue, type ActionCard, type ActionQueue } from '@/lib/api/actions';
import type { ForecastResponse, CashPositionResponse, FinancialRule } from '@/lib/api/types';

// Mock data based on AgencyCo demo account
const MOCK_ACTIONS: ActionQueue = {
  emergency: [
    {
      id: 'mock-action-1',
      action_type: 'invoice_follow_up',
      status: 'pending_approval',
      urgency: 'emergency',
      problem_summary: 'RetailCo Rebrand payment 14 days overdue',
      problem_context: 'Design milestone payment of $52,500 from RetailCo Rebrand is now 14 days overdue. This is unusual - the invoice was due on completion of design phase.',
      options: [
        {
          id: 'opt-1a',
          title: 'Send firm payment reminder',
          description: 'Send a firm but professional email requesting immediate payment',
          risk_level: 'medium',
          is_recommended: true,
          reasoning: ['Client is transactional (5.5% of revenue)', '14 days is significantly past usual pattern'],
          risk_score: 0.4,
          cash_impact: 52500,
          impact_description: 'Recover $52,500',
          prepared_content: {},
          success_probability: 0.75,
          display_order: 1,
        },
        {
          id: 'opt-1b',
          title: 'Send soft reminder',
          description: 'Send a gentle check-in to preserve relationship',
          risk_level: 'low',
          is_recommended: false,
          reasoning: ['Softer approach preserves relationship'],
          risk_score: 0.2,
          cash_impact: 52500,
          impact_description: 'Recover $52,500',
          prepared_content: {},
          success_probability: 0.5,
          display_order: 2,
        },
      ],
      created_at: new Date().toISOString(),
      deadline: new Date(Date.now() + 86400000).toISOString(),
      time_remaining: '1 day',
      linked_action_ids: [],
      entity_links: [
        { entity_type: 'client', entity_id: 'client_retailco', entity_name: 'RetailCo', route: '/clients-expenses' },
      ],
    },
  ],
  this_week: [
    {
      id: 'mock-action-2',
      action_type: 'payment_reminder',
      status: 'pending_approval',
      urgency: 'this_week',
      problem_summary: 'StartupX payment 12 days overdue',
      problem_context: 'Monthly retainer payment of $55,000 from StartupX is 12 days overdue. This is within their typical late payment pattern.',
      options: [
        {
          id: 'opt-2a',
          title: 'Send gentle reminder',
          description: 'Soft reminder appropriate for managed relationship',
          risk_level: 'low',
          is_recommended: true,
          reasoning: ['Client is managed relationship (8% of revenue)', '12 days is within normal pattern'],
          risk_score: 0.1,
          cash_impact: 55000,
          impact_description: 'Recover $55,000',
          prepared_content: {},
          success_probability: 0.8,
          display_order: 1,
        },
      ],
      created_at: new Date().toISOString(),
      deadline: new Date(Date.now() + 3 * 86400000).toISOString(),
      time_remaining: '3 days',
      linked_action_ids: [],
      entity_links: [
        { entity_type: 'client', entity_id: 'client_startupx', entity_name: 'StartupX', route: '/clients-expenses' },
      ],
    },
    {
      id: 'mock-action-3',
      action_type: 'payroll_confirmation',
      status: 'pending_approval',
      urgency: 'this_week',
      problem_summary: 'Payroll Safety Check: Friday $85K',
      problem_context: 'Bi-weekly payroll of $85,000 due Friday. Current cash covers payroll with $47K buffer. If RetailCo pays this week, buffer improves to $99K.',
      options: [
        {
          id: 'opt-3a',
          title: 'Confirm payroll',
          description: 'Cash is sufficient - confirm payroll and monitor collections',
          risk_level: 'low',
          is_recommended: true,
          reasoning: ['Cash is sufficient for payroll with buffer', 'Accelerating collections would improve buffer'],
          risk_score: 0.1,
          cash_impact: -85000,
          impact_description: 'Payroll expense',
          prepared_content: {},
          success_probability: 1.0,
          display_order: 1,
        },
      ],
      created_at: new Date().toISOString(),
      deadline: new Date(Date.now() + 4 * 86400000).toISOString(),
      time_remaining: '4 days',
      linked_action_ids: [],
      entity_links: [
        { entity_type: 'expense', entity_id: 'bucket_payroll', entity_name: 'Payroll', route: '/clients-expenses' },
      ],
    },
  ],
  upcoming: [
    {
      id: 'mock-action-4',
      action_type: 'statutory_payment',
      status: 'pending_approval',
      urgency: 'upcoming',
      problem_summary: 'Tax Payment Due: $22,000',
      problem_context: 'Q1 2026 Estimated Tax Payment of $22,000 is due in 18 days. Tax Reserve account has $50,000 - sufficient funds available.',
      options: [
        {
          id: 'opt-4a',
          title: 'Schedule tax payment',
          description: 'Schedule payment from Tax Reserve account',
          risk_level: 'low',
          is_recommended: true,
          reasoning: ['Tax Reserve has sufficient funds', 'Statutory deadline cannot be missed'],
          risk_score: 0.0,
          cash_impact: -22000,
          impact_description: 'Tax payment',
          prepared_content: {},
          success_probability: 1.0,
          display_order: 1,
        },
      ],
      created_at: new Date().toISOString(),
      deadline: new Date(Date.now() + 18 * 86400000).toISOString(),
      time_remaining: '18 days',
      linked_action_ids: [],
      entity_links: [
        { entity_type: 'expense', entity_id: 'bucket_tax', entity_name: 'Tax Reserve', route: '/clients-expenses' },
      ],
    },
    {
      id: 'mock-action-5',
      action_type: 'invoice_follow_up',
      status: 'pending_approval',
      urgency: 'upcoming',
      problem_summary: 'HealthTech Campaign payment 8 days overdue',
      problem_context: 'Execution milestone payment of $47,500 from HealthTech Campaign is 8 days overdue.',
      options: [
        {
          id: 'opt-5a',
          title: 'Send payment reminder',
          description: 'Professional reminder for milestone payment',
          risk_level: 'low',
          is_recommended: true,
          reasoning: ['Managed relationship', '8 days is moderate delay'],
          risk_score: 0.2,
          cash_impact: 47500,
          impact_description: 'Recover $47,500',
          prepared_content: {},
          success_probability: 0.7,
          display_order: 1,
        },
      ],
      created_at: new Date().toISOString(),
      deadline: new Date(Date.now() + 5 * 86400000).toISOString(),
      time_remaining: '5 days',
      linked_action_ids: [],
      entity_links: [
        { entity_type: 'client', entity_id: 'client_healthtech', entity_name: 'HealthTech', route: '/clients-expenses' },
      ],
    },
    {
      id: 'mock-action-6',
      action_type: 'invoice_follow_up',
      status: 'pending_approval',
      urgency: 'upcoming',
      problem_summary: 'LocalBiz Network payment 10 days overdue',
      problem_context: 'Monthly retainer payment of $25,000 from LocalBiz Network is 10 days overdue. Client has high churn risk.',
      options: [
        {
          id: 'opt-6a',
          title: 'Send careful reminder',
          description: 'Balanced reminder considering churn risk',
          risk_level: 'medium',
          is_recommended: true,
          reasoning: ['High churn risk client', 'Need to balance collection with retention'],
          risk_score: 0.3,
          cash_impact: 25000,
          impact_description: 'Recover $25,000',
          prepared_content: {},
          success_probability: 0.6,
          display_order: 1,
        },
      ],
      created_at: new Date().toISOString(),
      deadline: new Date(Date.now() + 7 * 86400000).toISOString(),
      time_remaining: '7 days',
      linked_action_ids: [],
      entity_links: [
        { entity_type: 'client', entity_id: 'client_localbiz', entity_name: 'LocalBiz Network', route: '/clients-expenses' },
      ],
    },
  ],
  emergency_count: 1,
  this_week_count: 2,
  upcoming_count: 3,
  total_count: 6,
};

const chartConfig = {
  endingBalance: {
    label: 'Ending Balance',
    color: 'var(--chart-1)',
  },
  cashBuffer: {
    label: 'Cash Buffer (Minimum)',
    color: 'var(--chart-3)',
  },
} satisfies ChartConfig;

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [cashPosition, setCashPosition] = useState<CashPositionResponse | null>(null);
  const [rules, setRules] = useState<FinancialRule[]>([]);
  const [actionQueue, setActionQueue] = useState<ActionQueue | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedAction, setSelectedAction] = useState<ActionCard | null>(null);

  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      try {
        const [forecastData, cashData, rulesData, actionsData] = await Promise.all([
          getForecast(user.id),
          getCashPosition(user.id),
          getRules(user.id).catch(() => []),
          getActionQueue().catch(() => null),
        ]);

        setForecast(forecastData);
        setCashPosition(cashData);
        setRules(rulesData);
        setActionQueue(actionsData);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [user]);

  // Calculate KPIs from backend data
  const availableCash = parseFloat(cashPosition?.total_starting_cash || '0');
  const hasData = forecast && forecast.weeks && forecast.weeks.length > 0;

  // Get total cash out from forecast summary (more reliable than summing individual weeks)
  const totalCashOut = forecast?.summary?.total_cash_out
    ? parseFloat(forecast.summary.total_cash_out)
    : 0;

  // Monthly expenses = total 13-week cash out / 3 months
  const monthlyExpenses = totalCashOut / 3;

  // Get buffer rule threshold (user-configurable, default 3 months)
  const bufferRule = rules.find((r) => r.rule_type === 'minimum_cash_buffer');
  const targetBufferMonths = (bufferRule?.threshold_config as { months?: number })?.months || 3;

  const bufferAmount = monthlyExpenses * targetBufferMonths;

  // Use runway_weeks from backend summary if available, otherwise calculate
  const runwayWeeks = forecast?.summary?.runway_weeks
    ? forecast.summary.runway_weeks
    : (monthlyExpenses > 0 ? Math.floor(availableCash / (monthlyExpenses / 4)) : 0);

  // Get lowest balance from backend summary
  const lowestBalance = forecast?.summary?.lowest_cash_amount
    ? parseFloat(forecast.summary.lowest_cash_amount)
    : availableCash;

  // Get the week with lowest cash (available for future UI display)
  const _lowestCashWeek = forecast?.summary?.lowest_cash_week || 0;
  void _lowestCashWeek; // Suppress unused warning - available for future use

  // Calculate buffer coverage in months
  const bufferCoverageMonths = monthlyExpenses > 0
    ? Math.max(0, lowestBalance / monthlyExpenses)
    : (lowestBalance > 0 ? 99 : 0);

  // Determine buffer status based on months of coverage
  // Urgent: less than 1 month, At Risk: less than target (default 3), Safe: meets or exceeds target
  const isUrgent = hasData && bufferCoverageMonths < 1;
  const isAtRisk = hasData && bufferCoverageMonths >= 1 && bufferCoverageMonths < targetBufferMonths;

  // Chart data
  const chartData = forecast?.weeks.map((week) => ({
    week: `W${week.week_number}`,
    endingBalance: parseFloat(week.ending_balance),
    cashIn: parseFloat(week.cash_in),
    cashOut: parseFloat(week.cash_out),
    cashBuffer: bufferAmount,
  })) || [];

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  // Use mock data as fallback when API returns no actions
  const effectiveActionQueue = actionQueue?.total_count ? actionQueue : MOCK_ACTIONS;

  // Get alerts from action queue (emergency + this_week actions)
  const recentAlerts = [
    ...(effectiveActionQueue.emergency || []),
    ...(effectiveActionQueue.this_week || []),
  ].slice(0, 3);

  // Get outstanding actions organized by week
  const actionsThisWeek = effectiveActionQueue.this_week || [];
  const actionsNextWeek = effectiveActionQueue.upcoming || [];

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-48" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="space-y-6 min-h-screen">
      {/* Page Title */}
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Top KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Current Cash */}
        <NeuroCard className="p-6 h-40 flex flex-col items-center justify-center">
          <div className="text-4xl font-bold text-gunmetal text-center">
            {formatCurrency(availableCash)}
          </div>
          <div className="text-sm font-medium text-gunmetal/60 text-center mt-2">
            Current Cash
          </div>
          <div className="text-xs text-gunmetal/40 text-center">(Today)</div>
        </NeuroCard>

        {/* Runway */}
        <NeuroCard className="p-6 h-40 flex flex-col items-center justify-center">
          <div className="text-4xl font-bold text-gunmetal text-center">
            {runwayWeeks > 52 ? '52+' : runwayWeeks}
          </div>
          <div className="text-sm font-medium text-gunmetal/60 text-center mt-2">
            Runway
          </div>
          <div className="text-xs text-gunmetal/40 text-center">(Weeks)</div>
        </NeuroCard>

        {/* Buffer Safety */}
        <NeuroCard className="p-6 h-40 relative flex flex-col items-center justify-center">
          {/* Info Icon with Tooltip */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="absolute top-3 right-3 text-gunmetal/30 hover:text-gunmetal/60 transition-colors">
                  <Info className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[220px] p-3">
                <p className="text-xs font-medium mb-2">Buffer Safety Levels:</p>
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-tomato" />
                    <span><strong>Urgent:</strong> Less than 1 month</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    <span><strong>At Risk:</strong> Less than 3 months</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-lime" />
                    <span><strong>Safe:</strong> 3+ months</span>
                  </div>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <div className="flex flex-col items-center justify-center">
            <div
              className={`text-4xl font-bold ${
                isUrgent
                  ? 'text-tomato'
                  : isAtRisk
                  ? 'text-amber-600'
                  : 'text-lime-dark'
              }`}
            >
              {isUrgent ? 'Urgent' : isAtRisk ? 'At Risk' : 'Safe'}
            </div>
            <div className="text-sm font-medium text-gunmetal/60 text-center mt-2">Buffer Status</div>
          </div>
        </NeuroCard>
      </div>

      {/* Recent Alerts */}
      {recentAlerts.length > 0 && (
        <NeuroCard>
          <NeuroCardHeader className="pb-3">
            <NeuroCardTitle>Recent Alerts</NeuroCardTitle>
          </NeuroCardHeader>
          <NeuroCardContent className="pt-0">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {recentAlerts.map((alert) => (
                <AlertCard key={alert.id} alert={alert} onViewAction={() => setSelectedAction(alert)} />
              ))}
            </div>
          </NeuroCardContent>
        </NeuroCard>
      )}

      {/* 13 Week Forecast Chart */}
      <NeuroCard>
        <NeuroCardHeader>
          <NeuroCardTitle>13 Week Forecast</NeuroCardTitle>
        </NeuroCardHeader>
        <NeuroCardContent>
          {chartData.length > 0 ? (
            <ChartContainer config={chartConfig} className="h-[350px] w-full">
              <ComposedChart
                data={chartData}
                margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="week"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                />
                <YAxis
                  tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                />
                <ChartTooltip
                  cursor={false}
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="rounded-xl border bg-white/90 backdrop-blur-sm p-4 shadow-xl">
                          <p className="font-semibold mb-2">{label}</p>
                          <div className="space-y-1 text-sm">
                            <div className="flex justify-between gap-4">
                              <span className="text-muted-foreground">Position:</span>
                              <span className="font-medium">{formatCurrency(data.endingBalance)}</span>
                            </div>
                            <div className="flex justify-between gap-4">
                              <span className="text-lime-dark">Income:</span>
                              <span className="font-medium text-lime-dark">+{formatCurrency(data.cashIn)}</span>
                            </div>
                            <div className="flex justify-between gap-4">
                              <span className="text-tomato">Expenses:</span>
                              <span className="font-medium text-tomato">-{formatCurrency(data.cashOut)}</span>
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <defs>
                  <linearGradient id="fillEndingBalance" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="endingBalance"
                  stroke="var(--chart-1)"
                  strokeWidth={2.5}
                  fill="url(#fillEndingBalance)"
                  fillOpacity={1}
                />
                {bufferAmount > 0 && (
                  <Line
                    type="monotone"
                    dataKey="cashBuffer"
                    stroke="#ef4444"
                    strokeDasharray="8 4"
                    strokeWidth={2}
                    dot={false}
                    activeDot={false}
                  />
                )}
              </ComposedChart>
            </ChartContainer>
          ) : (
            <div className="h-[350px] flex items-center justify-center text-muted-foreground">
              No forecast data available. Add clients and expenses to generate a forecast.
            </div>
          )}
          {/* Legend */}
          <div className="flex items-center justify-center gap-8 mt-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[var(--chart-1)]" />
              <span className="text-muted-foreground">Ending Balance</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-6 h-0.5 border-b-2 border-dashed border-red-500" />
              <span className="text-muted-foreground">Cash Buffer (Minimum)</span>
            </div>
          </div>
        </NeuroCardContent>
      </NeuroCard>

      {/* Outstanding Actions */}
      {(actionsThisWeek.length > 0 || actionsNextWeek.length > 0) && (
        <NeuroCard>
          <NeuroCardHeader className="flex flex-row items-center justify-between">
            <NeuroCardTitle>Outstanding Actions</NeuroCardTitle>
            <Button
              variant="ghost"
              size="sm"
              className="text-sm gap-1"
              onClick={() => navigate('/actions')}
            >
              View All Actions
              <ArrowRight className="w-4 h-4" />
            </Button>
          </NeuroCardHeader>
          <NeuroCardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Due This Week */}
              <div>
                <h3 className="text-sm font-semibold text-muted-foreground mb-4">Due This Week</h3>
                <div className="space-y-3">
                  {actionsThisWeek.slice(0, 3).map((action) => (
                    <ActionCardCompact
                      key={action.id}
                      action={action}
                      onView={() => setSelectedAction(action)}
                    />
                  ))}
                  {actionsThisWeek.length === 0 && (
                    <p className="text-sm text-muted-foreground">No actions due this week</p>
                  )}
                </div>
              </div>

              {/* Due Next Week */}
              <div>
                <h3 className="text-sm font-semibold text-muted-foreground mb-4">Due Next Week</h3>
                <div className="space-y-3">
                  {actionsNextWeek.slice(0, 3).map((action) => (
                    <ActionCardCompact
                      key={action.id}
                      action={action}
                      onView={() => setSelectedAction(action)}
                    />
                  ))}
                  {actionsNextWeek.length === 0 && (
                    <p className="text-sm text-muted-foreground">No actions due next week</p>
                  )}
                </div>
              </div>
            </div>
          </NeuroCardContent>
        </NeuroCard>
      )}

      {/* Action Detail Modal */}
      <ActionDetailModal
        action={selectedAction}
        onClose={() => setSelectedAction(null)}
        onApprove={(optionId) => {
          console.log('Approved option:', optionId);
          setSelectedAction(null);
        }}
        onReject={(optionId) => {
          console.log('Rejected option:', optionId);
        }}
      />
    </div>
  );
}

// Alert Card Component
interface AlertCardProps {
  alert: ActionCard;
  onViewAction: () => void;
}

function AlertCard({ alert, onViewAction }: AlertCardProps) {
  const navigate = useNavigate();
  const options = alert.options?.slice(0, 2) || [];
  const entityLinks = alert.entity_links || [];

  // Determine priority based on urgency
  const getPriorityConfig = () => {
    switch (alert.urgency) {
      case 'emergency':
        return { label: 'High', className: 'bg-tomato/15 text-tomato group-hover:bg-tomato/20' };
      case 'this_week':
        return { label: 'Medium', className: 'bg-amber-500/15 text-amber-600 group-hover:bg-amber-500/20' };
      default:
        return { label: 'Low', className: 'bg-lime/20 text-gunmetal/70 group-hover:bg-lime/30' };
    }
  };
  const priority = getPriorityConfig();

  // Handle entity link click (navigate without triggering onViewAction)
  const handleEntityClick = (e: React.MouseEvent, route: string, entityId: string) => {
    e.stopPropagation();
    // Navigate to the route with entity ID as query param for highlighting
    navigate(`${route}?highlight=${entityId}`);
  };

  return (
    <div
      className="group p-5 rounded-2xl bg-white/60 backdrop-blur-sm border border-white/40
                 hover:bg-white/80 hover:scale-[1.02] hover:shadow-lg hover:shadow-black/5
                 hover:border-white/60 cursor-pointer transition-all duration-300 ease-out"
      onClick={onViewAction}
    >
      {/* Header with title and badges */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <h4 className="font-semibold text-base text-gunmetal leading-tight group-hover:text-gunmetal/90 transition-colors">
          {alert.problem_summary}
        </h4>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium transition-colors ${priority.className}`}
          >
            {priority.label}
          </span>
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-lime/20 text-gunmetal/80 group-hover:bg-lime/30 transition-colors">
            Ready
          </span>
        </div>
      </div>

      {/* Entity links - show related clients/expenses */}
      {entityLinks.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-3 text-xs">
          <span className="text-gunmetal/50">Related:</span>
          {entityLinks.map((link, idx) => (
            <button
              key={`${link.entity_type}-${link.entity_id}-${idx}`}
              onClick={(e) => handleEntityClick(e, link.route, link.entity_id)}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                         bg-gunmetal/5 text-gunmetal/70 hover:bg-gunmetal/10 hover:text-gunmetal
                         transition-colors duration-200"
            >
              <span className="capitalize">{link.entity_type}:</span>
              <span className="font-medium">{link.entity_name}</span>
            </button>
          ))}
        </div>
      )}

      {/* Options list */}
      {options.length > 0 && (
        <div className="space-y-1.5 mb-4">
          {options.map((option, idx) => (
            <div key={option.id} className="flex items-start gap-2 text-sm text-gunmetal/70">
              <span className="font-medium text-gunmetal/50 w-16 flex-shrink-0">
                Option {String.fromCharCode(65 + idx)}
              </span>
              <span>{option.title}</span>
            </div>
          ))}
        </div>
      )}

      {/* Action link */}
      <div className="flex items-center gap-1 text-sm font-medium text-gunmetal/70 group-hover:text-tomato transition-colors">
        <span className="relative">
          View Action
          <span className="absolute bottom-0 left-0 w-0 h-[1px] bg-tomato group-hover:w-full transition-all duration-300" />
        </span>
        <ArrowRight className="w-3.5 h-3.5 transform group-hover:translate-x-1 transition-transform duration-300" />
      </div>
    </div>
  );
}

// Compact Action Card for Outstanding Actions section
interface ActionCardCompactProps {
  action: ActionCard;
  onView: () => void;
}

function ActionCardCompact({ action, onView }: ActionCardCompactProps) {
  const isUrgent = action.urgency === 'emergency';

  return (
    <div
      className="group p-4 rounded-xl bg-white/50 backdrop-blur-sm border border-white/30
                 hover:bg-white/70 hover:scale-[1.01] hover:shadow-md hover:shadow-black/5
                 hover:border-white/50 cursor-pointer transition-all duration-300 ease-out"
      onClick={onView}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <h4 className="font-medium text-sm text-gunmetal truncate group-hover:text-gunmetal/90 transition-colors">
              {action.problem_summary}
            </h4>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className={`px-1.5 py-0.5 rounded-full text-xs font-medium transition-colors ${
                isUrgent
                  ? 'bg-tomato/15 text-tomato group-hover:bg-tomato/20'
                  : 'bg-amber-500/15 text-amber-600 group-hover:bg-amber-500/20'
              }`}
            >
              {isUrgent ? 'Urgent' : 'Due Soon'}
            </span>
            <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-lime/20 text-gunmetal/70 group-hover:bg-lime/30 transition-colors">
              Ready
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1 text-xs font-medium text-gunmetal/60 group-hover:text-tomato transition-colors flex-shrink-0">
          <span>View</span>
          <ArrowRight className="w-3 h-3 transform group-hover:translate-x-0.5 transition-transform duration-300" />
        </div>
      </div>
    </div>
  );
}

// Action Detail Modal Component
interface ActionDetailModalProps {
  action: ActionCard | null;
  onClose: () => void;
  onApprove: (optionId: string) => void;
  onReject: (optionId: string) => void;
}

function ActionDetailModal({ action, onClose, onApprove, onReject }: ActionDetailModalProps) {
  const navigate = useNavigate();
  if (!action) return null;

  const isUrgent = action.urgency === 'emergency';
  const isDueToday = action.urgency === 'this_week';
  const entityLinks = action.entity_links || [];

  // Handle entity link click
  const handleEntityClick = (route: string, entityId: string) => {
    onClose();
    navigate(`${route}?highlight=${entityId}`);
  };

  // Format currency for display
  const formatCurrency = (value: number) => {
    if (Math.abs(value) >= 1000) {
      return `$${(Math.abs(value) / 1000).toFixed(0)}K`;
    }
    return `$${Math.abs(value).toLocaleString()}`;
  };

  // Parse problem context into bullet points
  const contextPoints = action.problem_context
    ? action.problem_context.split('. ').filter(Boolean).slice(0, 3)
    : [];

  return (
    <Dialog open={!!action} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto bg-white">
        {/* Header - Title left, badges right */}
        <DialogHeader className="pb-4 border-b border-gray-200">
          <div className="flex items-start justify-between gap-4">
            <DialogTitle className="text-lg font-semibold text-gunmetal leading-snug pr-2">
              {action.problem_summary}
            </DialogTitle>
            <div className="flex items-center gap-2 flex-shrink-0">
              {isUrgent && (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-tomato text-white">
                  Urgent
                </span>
              )}
              {(isUrgent || isDueToday) && (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-tomato text-white">
                  Due Today
                </span>
              )}
            </div>
          </div>
        </DialogHeader>

        {/* Context Section - Simple, no box */}
        <div className="py-4 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gunmetal mb-3">Context</h3>
          <ul className="space-y-2">
            {contextPoints.map((point, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-gunmetal/80">
                <span className="text-gunmetal/40 mt-0.5">•</span>
                <span>{point.trim()}</span>
              </li>
            ))}
          </ul>

          {/* Entity links */}
          {entityLinks.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-gunmetal/50">Related:</span>
                {entityLinks.map((link, idx) => (
                  <button
                    key={`${link.entity_type}-${link.entity_id}-${idx}`}
                    onClick={() => handleEntityClick(link.route, link.entity_id)}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full
                               bg-gunmetal/5 text-gunmetal/70 hover:bg-gunmetal/10 hover:text-gunmetal
                               transition-colors duration-200"
                  >
                    <span className="capitalize text-gunmetal/50">{link.entity_type}:</span>
                    <span className="font-medium">{link.entity_name}</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Your Options Section */}
        <div className="pt-4">
          <h3 className="text-sm font-semibold text-gunmetal mb-4">Your Options</h3>

          <div className="space-y-4">
            {action.options.map((option) => (
              <div
                key={option.id}
                className="p-4 rounded-lg border border-gray-200 bg-white"
              >
                {/* Option Title */}
                <h4 className="font-semibold text-gunmetal mb-2">
                  {option.title}
                  {option.cash_impact && ` (${formatCurrency(option.cash_impact)})`}
                </h4>

                {/* Badges row */}
                <div className="flex items-center gap-2 mb-3">
                  {option.is_recommended && (
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gunmetal/70">
                      Recommended
                    </span>
                  )}
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    option.risk_level === 'low'
                      ? 'bg-lime/20 text-gunmetal/70'
                      : option.risk_level === 'high'
                      ? 'bg-tomato/10 text-tomato'
                      : 'bg-amber-100 text-amber-700'
                  }`}>
                    {option.risk_level.charAt(0).toUpperCase() + option.risk_level.slice(1)} Risk
                  </span>
                </div>

                {/* Reasoning & Impact */}
                <ul className="space-y-1.5 mb-4">
                  {option.reasoning.map((reason, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-gunmetal/70">
                      <span className="text-gunmetal/40 mt-0.5">•</span>
                      <span>
                        <span className="text-gunmetal/50">Reasoning:</span> {reason}
                      </span>
                    </li>
                  ))}
                  {option.impact_description && (
                    <li className="flex items-start gap-2 text-sm text-gunmetal/70">
                      <span className="text-gunmetal/40 mt-0.5">•</span>
                      <span>
                        <span className="text-gunmetal/50">Impact:</span>{' '}
                        <span className="font-medium text-gunmetal">{option.impact_description}</span>
                      </span>
                    </li>
                  )}
                </ul>

                {/* Actions Row */}
                <div className="flex items-center justify-between gap-3 pt-3 border-t border-gray-100">
                  {/* View Draft button (left) */}
                  {(Object.keys(option.prepared_content).length > 0 || option.is_recommended) ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-gunmetal/60 hover:text-gunmetal hover:bg-gray-100 font-medium px-3"
                    >
                      <FileText className="w-4 h-4 mr-1.5" />
                      View Draft
                    </Button>
                  ) : (
                    <div />
                  )}

                  {/* Approve/Reject buttons (right) */}
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      className="bg-lime hover:bg-lime/90 text-gunmetal font-medium px-4"
                      onClick={() => onApprove(option.id)}
                    >
                      <Check className="w-4 h-4 mr-1.5" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-tomato/50 text-tomato hover:bg-tomato/10 font-medium px-4"
                      onClick={() => onReject(option.id)}
                    >
                      <X className="w-4 h-4 mr-1.5" />
                      Reject
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
